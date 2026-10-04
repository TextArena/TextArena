"""Game rollout collection for Tinker training.

Everything about *playing* games lives here: building prompts, sampling turns,
extracting <action>...</action> tags from model output, and the async workers
that keep games running. The training loop itself lives in train_selfplay.py.
"""
import json
import time
import random
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field

import tinker
import textarena as ta

log = logging.getLogger("tinker.rollouts")


@dataclass(frozen=True)
class EnvSpec:
    """A TextArena environment. Works for single-, two- and multi-player games."""
    env_id: str
    num_players: int = 2


@dataclass
class Turn:
    prompt_tokens: list[int]
    action_tokens: list[int]
    logprobs: list[float]  # sampler logprobs, one per action token
    ckpt: int              # checkpoint index this turn was sampled from
    has_action_tag: bool   # whether the model used <action>...</action>


@dataclass
class Trajectory:
    env_id: str
    pid: int
    turns: list[Turn] = field(default_factory=list)
    final_reward: float = 0.0
    invalid_move: bool = False


class Policy:
    """Shared handle to the newest sampling client; swapped by the learner after each update."""

    def __init__(self, client: tinker.SamplingClient):
        self.client, self.ckpt = client, 0

    def update(self, client: tinker.SamplingClient):
        self.client, self.ckpt = client, self.ckpt + 1


def build_prompt(tokenizer, instruction: str, observation: str) -> list[int]:
    content = f"{instruction}\n\nObservation: {observation}"
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True, tokenize=True)
    return tokenizer.encode(f"{content}\n\nAnswer: ")


def extract_action(text: str) -> tuple[str, bool]:
    """The action is the content of the last <action>...</action> tag; only that
    is submitted to the environment. Falls back to the raw text (no tag bonus)."""
    action = ta.extract_action(text)
    return action, action != text.strip()


async def play_game(
    spec: EnvSpec,
    policy: Policy,
    tokenizer,
    cfg,
    policy_pids: set[int] | None = None,
    opponent: tinker.SamplingClient | None = None,
) -> tuple[dict[int, Trajectory], dict[int, float], list[dict]]:
    """Play one game. Seats in `policy_pids` (default: all seats) are played by the current
    policy and collected; any remaining seats are played by `opponent`.
    Also returns a human-readable transcript of every turn (all seats)."""
    policy_pids = set(range(spec.num_players)) if policy_pids is None else policy_pids
    env = ta.make(spec.env_id)
    env.reset(num_players=spec.num_players)
    env.state.error_allowance = 0  # invalid moves end the game immediately
    trajs = {pid: Trajectory(env_id=spec.env_id, pid=pid) for pid in policy_pids}
    transcript: list[dict] = []
    sampling_params = tinker.SamplingParams(max_tokens=cfg.max_tokens, temperature=cfg.temperature, top_p=cfg.top_p)
    while True:
        pid, obs = env.get_observation()
        is_policy = pid in policy_pids
        client, ckpt = (policy.client, policy.ckpt) if is_policy else (opponent, -1)
        prompt_tokens = build_prompt(tokenizer, cfg.instruction, obs)
        resp = await client.sample_async(prompt=tinker.ModelInput.from_ints(prompt_tokens), num_samples=1, sampling_params=sampling_params)
        seq = resp.sequences[0]
        text = tokenizer.decode(seq.tokens)
        action, has_action_tag = extract_action(text)
        transcript.append({"pid": pid, "policy": is_policy, "ckpt": ckpt, "obs": obs, "output": text, "action": action})
        if is_policy:
            trajs[pid].turns.append(Turn(prompt_tokens, list(seq.tokens), list(seq.logprobs), ckpt, has_action_tag))
        done, _ = env.step(action)
        if done:
            break
    rewards, game_info = env.close()
    for pid, traj in trajs.items():
        traj.final_reward = float(rewards[pid])
        traj.invalid_move = bool(game_info.get(pid, {}).get("invalid_move", False))
    return trajs, {p: float(r) for p, r in rewards.items()}, transcript


def append_rollout(path: Path | None, kind: str, env_id: str, rewards: dict[int, float], transcript: list[dict]) -> None:
    """Append one finished game as a JSON line (view with e.g. `tail -f` or `jq`)."""
    if path is None:
        return
    record = {"time": time.time(), "kind": kind, "env_id": env_id, "rewards": rewards, "turns": transcript}
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


async def train_worker(cfg, policy: Policy, tokenizer, queue, rollout_path: Path | None) -> None:
    """Play mirror self-play games forever, pushing every seat's trajectory onto the queue."""
    while True:
        spec = random.choice(cfg.train_envs)
        try:
            trajs, rewards, transcript = await play_game(spec, policy, tokenizer, cfg)
        except Exception:
            log.exception(f"train game failed on {spec.env_id}")
            continue
        append_rollout(rollout_path, "train", spec.env_id, rewards, transcript)
        for traj in trajs.values():
            await queue.put(traj)


async def eval_worker(cfg, policy: Policy, base_client: tinker.SamplingClient, tokenizer, results: list, rollout_path: Path | None) -> None:
    """Play the current policy (one random seat) against the frozen step-0 weights."""
    while True:
        spec = random.choice(cfg.eval_envs)
        seat = random.randrange(spec.num_players)
        try:
            _, rewards, transcript = await play_game(spec, policy, tokenizer, cfg, policy_pids={seat}, opponent=base_client)
        except Exception:
            log.exception(f"eval game failed on {spec.env_id}")
            continue
        append_rollout(rollout_path, "eval", spec.env_id, rewards, transcript)
        others = [r for p, r in rewards.items() if p != seat]
        results.append({
            "env_id": spec.env_id,
            "reward": rewards[seat],
            "win": (rewards[seat] > max(others)) if others else None,  # None for single-player games
        })
