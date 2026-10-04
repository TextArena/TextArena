"""Train a reasoning model on TextArena games via mirror self-play, using Tinker.

A minimal async RL loop (REINFORCE with an EMA baseline and a sampler->trainer
importance-sampling correction). All heavy lifting (LoRA training, sampling,
checkpoints) runs on Tinker (https://tinker-docs.thinkingmachines.ai/), so this
script needs no GPUs and runs on a laptop.

How it works:
  * Game playing lives in rollouts.py: N workers play games concurrently. During
    training every seat is played by the newest policy checkpoint (mirror
    self-play) and every seat's trajectory is collected.
  * The model reasons freely, then puts its move inside <action>...</action>;
    only the tag content is submitted to the environment (ta.extract_action).
  * Advantage = final reward minus an EMA baseline keyed by (env, seat), so
    first-mover advantage is absorbed by the baseline.
  * Collection is asynchronous, so a turn may have been sampled a few checkpoints
    ago. Each action token stores its sampler logprob, and training uses Tinker's
    "importance_sampling" loss to correct for the off-policyness. The empirical
    KL(sampler||trainer) is logged; if it misbehaves, set loss_fn="ppo" or "cispo".
  * Eval games play the current policy against the frozen step-0 weights.
  * Every finished game is appended to rollouts/<run_name>/games.jsonl for easy
    inspection.

Use the "-mdp" variant of environments: each observation then contains the
complete game state, so turns can be treated as independent prompts.

Requires: pip install tinker textarena numpy   (and: export TINKER_API_KEY=...)
"""
import time
import asyncio
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import tinker

from rollouts import EnvSpec, Policy, Trajectory, train_worker, eval_worker

DEFAULT_INSTRUCTION = (
    "You are playing a game. Make valid actions to win. "
    "Reason step by step, then put your final action inside <action>...</action> tags; "
    "only the content inside the tags is submitted to the game."
)


@dataclass
class Config:
    # model
    model_name: str = "thinkingmachines/Inkling-Small"
    lora_rank: int = 32

    # environments (during training every seat is played by the current policy)
    train_envs: list[EnvSpec] = field(default_factory=lambda: [EnvSpec("SimpleTak-v0-mdp")])
    eval_envs: list[EnvSpec] = field(default_factory=list)  # policy vs. frozen step-0 weights

    # optimization
    learning_steps: int = 200
    batch_size: int = 384                   # turns (datums) per learner update
    learning_rate: float = 1e-5
    grad_clip_norm: float = 0.2
    loss_fn: str = "importance_sampling"    # sampler->trainer off-policy correction

    # sampling
    max_tokens: int = 4096                  # generation budget per turn
    temperature: float = 0.6
    top_p: float = 0.95
    max_seq_len: int = 8192                 # turns whose prompt+action exceed this are skipped

    # collection
    num_train_workers: int = 64             # concurrent self-play games
    num_eval_workers: int = 8               # concurrent eval games
    max_staleness: int = 4                  # drop turns sampled more than N checkpoints ago

    # rewards
    ema_beta: float = 0.99                  # baseline: EMA of final rewards, keyed by (env_id, seat)
    format_bonus: float = 0.25              # +/- for producing (or not) an <action>...</action> tag
    invalid_move_penalty: float = 1.0       # extra penalty on the turn that ended the game invalidly

    # prompting / logging
    instruction: str = DEFAULT_INSTRUCTION
    wandb_project: str | None = None
    run_name: str | None = None
    rollout_dir: str | None = "rollouts"    # game transcripts as JSONL; None disables
    save_state_every: int = 0               # save a resumable training-client state every N steps; 0 disables


def traj_to_datums(traj: Trajectory, advantage: float, cfg: Config, current_ckpt: int) -> list[tinker.Datum]:
    """One datum per turn: prompt tokens are masked out, action tokens carry the trajectory
    advantage plus per-turn shaping, and the sampler logprobs enable the off-policy correction."""
    datums = []
    for turn in traj.turns:
        if current_ckpt - turn.ckpt > cfg.max_staleness:
            continue
        tokens = turn.prompt_tokens + turn.action_tokens
        if len(tokens) > cfg.max_seq_len:
            continue
        adv = advantage + (cfg.format_bonus if turn.has_action_tag else -cfg.format_bonus)
        if traj.invalid_move and turn is traj.turns[-1]:
            adv -= cfg.invalid_move_penalty
        pad = len(turn.prompt_tokens) - 1  # positions that predict prompt tokens
        n_action = len(turn.action_tokens)
        datums.append(tinker.Datum(
            model_input=tinker.ModelInput.from_ints(tokens[:-1]),
            loss_fn_inputs={
                "target_tokens": tokens[1:],
                "weights": [0.0] * pad + [1.0] * n_action,
                "logprobs": [0.0] * pad + list(turn.logprobs),
                "advantages": [0.0] * pad + [adv] * n_action,
            },
        ))
    return datums


def sampler_trainer_kl(datums: list[tinker.Datum], fb_result) -> float:
    """Mean per-token KL(sampler || trainer) over action tokens, from the training forward pass."""
    kls = []
    for datum, out in zip(datums, fb_result.loss_fn_outputs):
        trainer_lp = out["logprobs"].to_numpy()
        sampler_lp = datum.loss_fn_inputs["logprobs"].to_numpy()
        mask = datum.loss_fn_inputs["weights"].to_numpy() > 0
        if mask.any():
            kls.append(float((sampler_lp[mask] - trainer_lp[mask]).mean()))
    return float(np.mean(kls)) if kls else float("nan")


async def train(cfg: Config) -> None:
    run_name = cfg.run_name or f"selfplay-{cfg.model_name.split('/')[-1]}-{int(time.time())}"
    wandb_run = None
    if cfg.wandb_project:
        import wandb
        wandb_run = wandb.init(project=cfg.wandb_project, name=run_name, config=vars(cfg))

    service = tinker.ServiceClient()
    trainer = service.create_lora_training_client(base_model=cfg.model_name, rank=cfg.lora_rank)
    tokenizer = trainer.get_tokenizer()
    base_client = await trainer.save_weights_and_get_sampling_client_async(name=f"{run_name}-base")
    policy = Policy(base_client)

    rollout_path = None
    if cfg.rollout_dir:
        rollout_path = Path(cfg.rollout_dir) / run_name / "games.jsonl"
        rollout_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"storing game transcripts in {rollout_path}")

    # bounded queue: workers pause instead of sampling turns that would only go stale
    queue: asyncio.Queue[Trajectory] = asyncio.Queue(maxsize=cfg.batch_size * 2)
    eval_results: list[dict] = []
    workers = [asyncio.create_task(train_worker(cfg, policy, tokenizer, queue, rollout_path)) for _ in range(cfg.num_train_workers)]
    if cfg.eval_envs:
        workers += [asyncio.create_task(eval_worker(cfg, policy, base_client, tokenizer, eval_results, rollout_path)) for _ in range(cfg.num_eval_workers)]

    ema: dict[tuple[str, int], float] = defaultdict(float)
    adam_params = tinker.AdamParams(learning_rate=cfg.learning_rate, grad_clip_norm=cfg.grad_clip_norm)

    try:
        for step in range(1, cfg.learning_steps + 1):
            # pull trajectories until we have a full batch of turns
            datums, rewards, n_turns, n_tagged, n_invalid, n_trajs = [], [], 0, 0, 0, 0
            while len(datums) < cfg.batch_size:
                traj = await queue.get()
                key = (traj.env_id, traj.pid)
                advantage = traj.final_reward - ema[key]
                ema[key] += (1 - cfg.ema_beta) * (traj.final_reward - ema[key])
                datums += traj_to_datums(traj, advantage, cfg, policy.ckpt)
                rewards.append(traj.final_reward)
                n_turns += len(traj.turns)
                n_tagged += sum(t.has_action_tag for t in traj.turns)
                n_invalid += traj.invalid_move
                n_trajs += 1

            # forward/backward with sampler->trainer importance correction, then update & swap the sampler
            fb_future = await trainer.forward_backward_async(datums, cfg.loss_fn)
            optim_future = await trainer.optim_step_async(adam_params)
            fb_result = await fb_future.result_async()
            await optim_future.result_async()
            policy.update(await trainer.save_weights_and_get_sampling_client_async())

            metrics = {
                "step": step,
                "reward_mean": float(np.mean(rewards)),
                "kl_sampler_trainer": sampler_trainer_kl(datums, fb_result),
                "num_datums": len(datums),
                "num_trajectories": n_trajs,
                "turns_per_trajectory": n_turns / max(n_trajs, 1),
                "action_tag_rate": n_tagged / max(n_turns, 1),
                "invalid_move_rate": n_invalid / max(n_trajs, 1),
            }
            metrics |= {f"ema/{env_id}-p{pid}": v for (env_id, pid), v in ema.items()}
            if eval_results:
                by_env: dict[str, list[dict]] = defaultdict(list)
                for r in eval_results:
                    by_env[r["env_id"]].append(r)
                for env_id, rs in by_env.items():
                    metrics[f"eval/{env_id}-reward"] = float(np.mean([r["reward"] for r in rs]))
                    wins = [r["win"] for r in rs if r["win"] is not None]
                    if wins:
                        metrics[f"eval/{env_id}-winrate"] = float(np.mean(wins))
                    metrics[f"eval/{env_id}-games"] = len(rs)
                eval_results.clear()

            print(f"[{run_name}] " + " | ".join(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}" for k, v in metrics.items()))
            if wandb_run:
                wandb_run.log(metrics)

            if cfg.save_state_every and step % cfg.save_state_every == 0:
                state_future = await trainer.save_state_async(name=f"{run_name}-step{step}")
                print(f"saved resumable state: {(await state_future.result_async()).path}")
    finally:
        for w in workers:
            w.cancel()
        if wandb_run:
            wandb_run.finish()


if __name__ == "__main__":
    asyncio.run(train(Config(
        model_name="thinkingmachines/Inkling-Small",
        train_envs=[EnvSpec("SimpleTak-v0-mdp", num_players=2)],
        eval_envs=[EnvSpec("SimpleTak-v0-mdp", num_players=2), EnvSpec("KuhnPoker-v0-mdp", num_players=2)],
        wandb_project=None,  # set to a project name to enable wandb logging
    )))
