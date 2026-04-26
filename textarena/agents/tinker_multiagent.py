"""
tinker_multiagent.py — Multi-agent RL training for Avalon with Tinker.

Two-stage pipeline
------------------
1. **SFT warm-start (optional)** — self-distillation from
   ``results/reflection_memory.json``.  Each lesson becomes one
   ``(system, user, assistant)`` demonstration so the policy enters RL with
   accumulated wisdom baked in.  Skipped when the file is absent or
   ``--skip-sft`` is passed.

2. **5-player Avalon self-play GRPO**.  All five players share one LoRA-
   adapted policy.  Per training step we run G parallel games; the rollouts
   produce 5 trajectories per game; advantages are mean-centred within
   each role bucket (Good / Evil) and standardised globally before the
   policy update.

Prompt distribution alignment
-----------------------------
Both the rollout coordinator and ``TinkerDistilAgent`` (the inference-time
agent in ``tinker_distil_agent.py``) use the *same* prompt builders imported
from ``deeprole_llm.py``:

  * ``_dr_build_llm_prompt`` for ordinary phases
  * ``_dr_build_merlin_guess_prompt`` for the Guess-Merlin end-game

So the trained adapter is consumed at inference exactly the way it was
trained, and tweaks to the prompt format only need to happen in one place.

Checkpoints
-----------
Every ``--save-every`` steps, the script saves sampler weights via
``training_client.save_weights_for_sampler_async(name=...)``.  The returned
path looks like ``tinker://UUID:train:0/sampler_weights/00040`` and can be
fed straight into ``TinkerDistilAgent(tinker_model_path=...)`` for
evaluation.

References
----------
  Multi-agent RL overview:
    https://tinker-docs.thinkingmachines.ai/cookbook/recipes/multiplayer-rl/
  Cookbook source (use as reference for exact SDK signatures):
    https://github.com/thinking-machines-lab/tinker-cookbook/tree/main/
    tinker_cookbook/recipes/multiplayer_rl/

Run
---
    export TINKER_API_KEY=<your-key>
    python tinker_multiagent.py \\
        --base-model meta-llama/Llama-3.2-1B \\
        --lora-rank 32 \\
        --games-per-step 8 \\
        --steps 100

    # Skip SFT, do RL only:
    python tinker_multiagent.py --skip-sft

NOTE: Tinker's ``Env`` / coordinator / loss-function API has minor version
drift between cookbook releases.  Lines marked ``# VERIFY:`` are where
integration bugs are most likely; cross-reference with your installed
tinker_cookbook version when first running.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Path setup — prefer local textarena/ over site-packages
# ---------------------------------------------------------------------------

# Script lives at <repo>/textarena/agents/tinker_multiagent.py.
# parent.parent.parent walks up to the repo root so the local textarena/
# package wins over any site-packages install (PyPI builds omit Avalon-v0).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# .env loader (stdlib only — no python-dotenv required)
# ---------------------------------------------------------------------------

def _load_env_file(path: Path) -> None:
    """Set os.environ from KEY=value lines; does not override existing vars."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


_load_env_file(_REPO_ROOT / ".env")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("tinker_multiagent")


# ===========================================================================
# Reward shaping (matches multi_play.py)
# ===========================================================================

_GOOD_ROLES = frozenset({"Servant", "Merlin", "Percival"})
_EVIL_ROLES = frozenset({"Minion", "Morgana", "Mordred", "Assassin", "Oberon"})


def role_aware_reward(role: Optional[str], env_reward: float) -> float:
    """+0.4/-0.4 Good win/loss · +0.6/-0.6 Evil win/loss · raw env_reward otherwise."""
    if role is None:
        return float(env_reward)
    won = env_reward > 0
    if role in _GOOD_ROLES:
        return 0.4 if won else -0.4
    if role in _EVIL_ROLES:
        return 0.6 if won else -0.6
    return float(env_reward)


# ===========================================================================
# Config
# ===========================================================================

@dataclass
class TrainerConfig:
    # Model
    base_model:       str   = "meta-llama/Llama-3.2-1B"
    lora_rank:        int   = 32
    renderer_name:    str   = "llama3"        # match base model: "llama3" / "qwen3" / "role_colon"
    learning_rate:    float = 2e-5

    # Rollout
    games_per_step:   int   = 8               # G dimension
    num_players:      int   = 5
    max_new_tokens:   int   = 128
    temperature:      float = 0.9
    env_id:           str   = "Avalon-v0"
    special_roles:    Optional[List[str]] = field(
        default_factory=lambda: ["Merlin", "Morgana"]
    )

    # CFR (forwarded to integrator inside each rollout)
    cfr_iterations:      Optional[int] = 50
    cfr_wait_iterations: Optional[int] = 25

    # Training
    steps:            int   = 100
    save_every:       int   = 20

    # SFT warm-start
    skip_sft:         bool  = False
    sft_epochs:       int   = 1
    sft_lr:           float = 1e-5

    # Reflection memory (SFT data source)
    memory_path:      str   = "results/reflection_memory.json"
    cheat_sheet_k:    int   = 5

    # Output
    run_name:         Optional[str] = None
    out_dir:          str           = "results/tinker_avalon"


# ===========================================================================
# Avalon env wrapper (single-game, async)
# ===========================================================================

class AvalonEnv:
    """
    Single-game Avalon environment wrapping ``textarena.make("Avalon-v0")``.
    Single-use, matching Tinker's env lifecycle (no reset).
    """

    def __init__(
        self,
        seed: int,
        env_id: str = "Avalon-v0",
        special_roles: Optional[List[str]] = None,
        num_players: int = 5,
    ):
        import textarena as ta
        self._env = ta.make(env_id=env_id)
        if special_roles:
            self._env.reset(
                num_players=num_players,
                special_roles=set(special_roles),
                seed=seed,
            )
        else:
            self._env.reset(num_players=num_players, seed=seed)
        self._num_players = num_players
        self._seed        = seed
        self._done        = False
        self._per_player_rewards: Dict[int, float] = {i: 0.0 for i in range(num_players)}
        self._roles:              Dict[int, str]   = {}

    async def initial_observation(self) -> Tuple[int, str]:
        """Return ``(player_id, observation_string)`` for the first turn."""
        player_id, obs = self._env.get_observation()
        return int(player_id), str(obs)

    async def step(self, action: str) -> Tuple[int, str, bool, Dict[int, float]]:
        """Apply ``action``; return ``(next_pid, next_obs, done, terminal_rewards)``."""
        done, _step_info = self._env.step(action=action)
        self._done = bool(done)

        if self._done:
            rewards, game_info = self._env.close()
            for k, v in (rewards or {}).items():
                try:
                    self._per_player_rewards[int(k)] = float(v)
                except (TypeError, ValueError):
                    continue
            for pid, info in (game_info or {}).items():
                if isinstance(info, dict):
                    role = info.get("role")
                    if isinstance(role, str):
                        try:
                            self._roles[int(pid)] = role
                        except (TypeError, ValueError):
                            pass
            return -1, "", True, dict(self._per_player_rewards)

        next_player, next_obs = self._env.get_observation()
        return int(next_player), str(next_obs), False, {}

    def roles(self) -> Dict[int, str]:
        return dict(self._roles)

    @property
    def num_players(self) -> int:
        return self._num_players


# ===========================================================================
# 5-player coordinator
# ===========================================================================

@dataclass
class PlayerTrajectory:
    """One player's trajectory within a single game."""
    player_id:    int
    role:         str
    messages:     List[Dict[str, str]] = field(default_factory=list)
    actions:      List[str]            = field(default_factory=list)
    reward:       float                = 0.0
    env_reward:   float                = 0.0


class NPlayerCoordinator:
    """
    Drives one ``AvalonEnv`` to completion by sampling from a shared policy.

    All players share one LoRA-adapted model; per-player state (conversation
    history) is tracked independently so each trajectory captures only that
    player's turns.

    Prompts are built using the *same* helpers ``DeepRoleLLMAgent`` uses at
    inference, so the trained adapter sees the same distribution at deploy
    time as at training time.
    """

    def __init__(
        self,
        env: AvalonEnv,
        sampling_client: Any,    # tinker.SamplingClient
        renderer:        Any,    # tinker_cookbook renderer
        cheat_sheet:     str = "",
        max_new_tokens:  int = 128,
        temperature:     float = 0.9,
        cfr_iterations:      Optional[int] = 50,
        cfr_wait_iterations: Optional[int] = 25,
    ):
        from textarena.agents.deeprole_llm import (
            _InstrumentedDeepRoleIntegrator,
            _dr_build_hidden_state_table,
        )

        self.env             = env
        self.sampling_client = sampling_client
        self.renderer        = renderer
        self.cheat_sheet     = cheat_sheet
        self.max_new_tokens  = max_new_tokens
        self.temperature     = temperature

        # One DeepRole integrator per game — drives belief / strategy / role.
        self._integrator = _InstrumentedDeepRoleIntegrator(
            iterations=cfr_iterations, wait_iterations=cfr_wait_iterations,
        )
        self._id_to_hid = _dr_build_hidden_state_table()

        # Per-player conversation history; each player only sees turns
        # addressed to them.
        self._histories: Dict[int, List[Dict[str, str]]] = {
            i: [] for i in range(env.num_players)
        }

    # ------------------------------------------------------------------
    # Prompt construction — delegates to deeprole_llm helpers
    # ------------------------------------------------------------------

    def _build_prompt_for_turn(
        self, observation_text: str
    ) -> Tuple[str, str, str, int]:
        """
        Build (system, user, role, player_id) for the active turn.

        Routes Guess-Merlin to the dedicated builder; everything else to the
        ordinary belief+message prompt.  Both come from ``deeprole_llm``.
        """
        from textarena.agents.deeprole_integrator import dr_parse_game_states, dr_phase_str
        from textarena.agents.deeprole_llm import (
            _dr_is_guess_merlin_phase,
            _dr_player_evil_probs,
            _dr_player_merlin_probs,
            _dr_get_evil_teammate,
            _dr_parse_teammate_from_obs,
            _dr_is_belief_informative,
            _dr_build_llm_prompt,
            _dr_build_merlin_guess_prompt,
        )

        # Run the integrator to populate belief / role / player.
        self._integrator(observation_text)
        belief_vec = self._integrator.exposed_belief
        player     = self._integrator.exposed_player
        role       = self._integrator.exposed_role
        dr_action  = self._integrator.exposed_dr_action

        snaps = dr_parse_game_states(observation_text)
        gs    = snaps[-1] if snaps else {}
        phase = dr_phase_str(gs) if gs else "unknown"
        evil_probs = _dr_player_evil_probs(belief_vec, self._id_to_hid)

        # Guess-Merlin path
        if _dr_is_guess_merlin_phase(gs, observation_text):
            teammate: Optional[int] = None
            if _dr_is_belief_informative(belief_vec):
                try:
                    teammate = _dr_get_evil_teammate(belief_vec, self._id_to_hid, player)
                except Exception:
                    teammate = None
            if teammate is None:
                try:
                    teammate = _dr_parse_teammate_from_obs(observation_text, player)
                except Exception:
                    teammate = None

            exclude    = {player} | ({teammate} if teammate is not None else set())
            candidates = [p for p in range(self.env.num_players) if p not in exclude]
            try:
                merlin_probs = _dr_player_merlin_probs(belief_vec, self._id_to_hid)
            except Exception:
                merlin_probs = [0.0] * self.env.num_players

            sys_p, usr_p = _dr_build_merlin_guess_prompt(
                player_id=player, role=role, teammate_id=teammate,
                candidates=candidates, merlin_probs=merlin_probs,
                game_state=gs, observation_text=observation_text,
            )
        else:
            sys_p, usr_p = _dr_build_llm_prompt(
                player_id=player, role=role, phase=phase, game_state=gs,
                player_evil_probs=evil_probs, dr_action=dr_action,
                observation_text=observation_text,
            )

        # Optionally append cheat sheet to the system prompt — keeps the
        # current ``_dr_build_llm_prompt`` signature unchanged.
        if self.cheat_sheet:
            sys_p = (
                sys_p
                + "\n\nLessons learned from past games (apply when relevant):\n"
                + self.cheat_sheet
            )

        return sys_p, usr_p, role, player

    # ------------------------------------------------------------------
    # Rollout
    # ------------------------------------------------------------------

    async def rollout(self) -> List[PlayerTrajectory]:
        """Run one game to termination; return one trajectory per player."""
        player_id, obs = await self.env.initial_observation()
        trajectories: Dict[int, PlayerTrajectory] = {
            i: PlayerTrajectory(player_id=i, role="")
            for i in range(self.env.num_players)
        }

        done       = False
        step_count = 0
        MAX_STEPS  = 512

        while not done and step_count < MAX_STEPS:
            step_count += 1

            sys_p, usr_p, role, active = self._build_prompt_for_turn(obs)

            # Persist per-player conversation: when this is the first turn for
            # a player, seed it with the system prompt; otherwise just append
            # the new user message.  This keeps each player's context window
            # focused on their own turns.
            hist = self._histories[active]
            if not hist:
                hist.append({"role": "system", "content": sys_p})
            hist.append({"role": "user", "content": usr_p})

            action_text = await self._sample_action(hist)

            hist.append({"role": "assistant", "content": action_text})
            trajectories[active].actions.append(action_text)

            next_pid, next_obs, done, terminal_rewards = await self.env.step(action_text)

            if done:
                roles = self.env.roles()
                for pid, traj in trajectories.items():
                    traj.role       = roles.get(pid, "")
                    traj.env_reward = float(terminal_rewards.get(pid, 0.0))
                    traj.reward     = role_aware_reward(traj.role, traj.env_reward)
                    traj.messages   = list(self._histories[pid])
                break

            player_id, obs = next_pid, next_obs

        return list(trajectories.values())

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    async def _sample_action(self, messages: List[Dict[str, str]]) -> str:
        """
        Sample one assistant turn from the shared policy via Tinker.

        TinkerMessageCompleter exposes ``async __call__(messages) -> Message``
        per the cookbook docs; we invoke it via the standard call syntax.
        Falls back to the low-level ``sample_async`` only if the cookbook
        completer is unavailable.
        """
        # Pattern A — MessageCompleter (cookbook >= 0.2)
        try:
            from tinker_cookbook.completers import TinkerMessageCompleter  # noqa: WPS433
            completer = TinkerMessageCompleter(
                sampling_client = self.sampling_client,
                renderer        = self.renderer,
                max_tokens      = self.max_new_tokens,
                temperature     = self.temperature,
            )
            reply = await completer(messages)   # __call__, not .complete
            # Reply is a Message dataclass with a `content` field; fall back
            # to str() in case the cookbook ever changes the shape.
            return reply.content if hasattr(reply, "content") else str(reply)
        except ImportError:
            pass

        # Pattern B — low-level sample_async
        import tinker
        prompt_tokens   = self.renderer.build_generation_prompt(messages)
        sampling_params = tinker.types.SamplingParams(
            max_tokens  = self.max_new_tokens,
            temperature = self.temperature,
        )
        sample_resp = await self.sampling_client.sample_async(
            prompt          = tinker.types.ModelInput.from_ints(prompt_tokens),
            sampling_params = sampling_params,
            num_samples     = 1,
        )
        out_tokens = sample_resp.sequences[0].tokens
        return self.renderer.tokenizer.decode(out_tokens, skip_special_tokens=True)


# ===========================================================================
# SFT warm-start from ReflectionMemory
# ===========================================================================

def build_sft_examples_from_memory(memory_path: Path) -> List[Dict[str, str]]:
    """
    Expand reflection-memory lessons into supervised demos:
        system    : "You are an expert Avalon player sharing strategy advice."
        user      : "Share one key principle for playing Avalon (context: ...)"
        assistant : <lesson text>
    Returns [] when the file is absent or unparseable.
    """
    if not memory_path.is_file():
        log.info(f"No reflection memory at {memory_path} — skipping SFT warm-start.")
        return []

    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.warning(f"Could not parse memory file: {e}")
        return []

    lessons = data.get("lessons") or []
    examples: List[Dict[str, str]] = []
    for entry in lessons:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        role = str(entry.get("role_context", "")).strip()
        suffix = f" (context: playing {role})" if role else ""
        examples.append({
            "system":    "You are an expert Avalon player sharing strategy advice.",
            "user":      f"Share one key principle for playing Avalon{suffix}.",
            "assistant": text,
        })

    log.info(f"Built {len(examples)} SFT examples from reflection memory.")
    return examples


async def sft_warm_start(
    training_client: Any,
    renderer:        Any,
    examples:        List[Dict[str, str]],
    *,
    epochs: int   = 1,
    lr:     float = 1e-5,
) -> None:
    """
    Short SFT pass over memory-derived examples.  For production-grade SFT
    use ``tinker_cookbook.supervised.train`` instead — this is a thin loop
    suitable for the small lesson corpus.
    """
    if not examples:
        return
    log.info(f"SFT warm-start: {len(examples)} examples × {epochs} epoch(s), lr={lr}")

    for epoch in range(epochs):
        for i, ex in enumerate(examples):
            msgs = [
                {"role": "system",    "content": ex["system"]},
                {"role": "user",      "content": ex["user"]},
                {"role": "assistant", "content": ex["assistant"]},
            ]
            # VERIFY: build_supervised_example signature (renderer-specific)
            model_input, _weights = renderer.build_supervised_example(msgs)
            await training_client.forward_backward_async(
                data_batch = [model_input],
                loss_fn    = "cross_entropy",
            )
            await training_client.optim_step_async(
                adam_params = {"lr": lr, "beta1": 0.9, "beta2": 0.95, "eps": 1e-8}
            )
            if (i + 1) % 16 == 0:
                log.info(f"  sft epoch={epoch} step={i+1}/{len(examples)}")


# ===========================================================================
# Cheat sheet from memory (used as RL-time prompt augmentation)
# ===========================================================================

def load_cheat_sheet(memory_path: Path, k: int) -> str:
    """Load the top-K lessons as a formatted block for the system prompt."""
    if not memory_path.is_file() or k <= 0:
        return ""
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    lessons = data.get("lessons") or []
    top = sorted(
        lessons,
        key=lambda l: (l.get("cite_count", 1), l.get("last_seen_ts", 0.0)),
        reverse=True,
    )[:k]
    return "\n".join(f"- {l.get('text', '').strip()}" for l in top if l.get("text"))


# ===========================================================================
# RL training loop
# ===========================================================================

async def rl_train(cfg: TrainerConfig) -> None:
    """5-player Avalon self-play RL with role-aware GRPO advantages."""
    try:
        import tinker  # noqa: F401 — types referenced below
        from tinker_cookbook.renderers import get_renderer
        from transformers import AutoTokenizer
    except ImportError as e:
        raise ImportError(
            "tinker, tinker_cookbook, and transformers are required.  Install:\n"
            "    pip install 'tinker-cookbook[multiplayer-rl]' transformers\n"
            f"Original error: {e}"
        )

    if not os.getenv("TINKER_API_KEY"):
        raise SystemExit("TINKER_API_KEY not set.")

    out_dir = Path(cfg.out_dir)
    if cfg.run_name:
        out_dir = out_dir / cfg.run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Run dir: {out_dir}")

    # ------------------------------------------------------------------
    # Tinker clients (use async variants — we are inside asyncio.run)
    # ------------------------------------------------------------------
    service_client  = tinker.ServiceClient()
    training_client = await service_client.create_lora_training_client_async(
        base_model = cfg.base_model,
        rank       = cfg.lora_rank,
    )
    # Renderer needs a tokenizer matching the base model so prompts/output
    # tokens align with what the training client expects.
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    renderer  = get_renderer(cfg.renderer_name, tokenizer)

    # ------------------------------------------------------------------
    # Cheat sheet (used for both SFT context and RL-time prompts)
    # ------------------------------------------------------------------
    memory_path = Path(cfg.memory_path)
    cheat_sheet = load_cheat_sheet(memory_path, cfg.cheat_sheet_k)
    if cheat_sheet:
        log.info(f"Loaded cheat sheet ({cheat_sheet.count(chr(10))+1} lessons).")

    # ------------------------------------------------------------------
    # Stage 1 — SFT warm-start
    # ------------------------------------------------------------------
    if not cfg.skip_sft:
        examples = build_sft_examples_from_memory(memory_path)
        if examples:
            await sft_warm_start(
                training_client, renderer, examples,
                epochs=cfg.sft_epochs, lr=cfg.sft_lr,
            )

    # ------------------------------------------------------------------
    # Stage 2 — RL self-play
    # ------------------------------------------------------------------
    for step in range(cfg.steps):
        log.info(f"--- step {step+1}/{cfg.steps} ---")

        # Fresh sampler from current weights.
        sampling_client = await training_client.save_weights_and_get_sampling_client_async()

        # G parallel games.
        envs = [
            AvalonEnv(
                seed          = step * cfg.games_per_step + g,
                env_id        = cfg.env_id,
                special_roles = cfg.special_roles,
                num_players   = cfg.num_players,
            )
            for g in range(cfg.games_per_step)
        ]
        coordinators = [
            NPlayerCoordinator(
                env                 = e,
                sampling_client     = sampling_client,
                renderer            = renderer,
                cheat_sheet         = cheat_sheet,
                max_new_tokens      = cfg.max_new_tokens,
                temperature         = cfg.temperature,
                cfr_iterations      = cfg.cfr_iterations,
                cfr_wait_iterations = cfg.cfr_wait_iterations,
            )
            for e in envs
        ]
        all_trajs: List[List[PlayerTrajectory]] = await asyncio.gather(
            *(c.rollout() for c in coordinators)
        )

        # Flatten: 5G trajectories total.
        flat: List[PlayerTrajectory] = [t for g in all_trajs for t in g]

        # Role-aware advantage: mean-centre within Good / Evil buckets.
        rewards_by_bucket: Dict[str, List[float]] = {}
        def bucket_of(role: str) -> str:
            if role in _GOOD_ROLES: return "good"
            if role in _EVIL_ROLES: return "evil"
            return "other"
        for t in flat:
            rewards_by_bucket.setdefault(bucket_of(t.role), []).append(t.reward)
        bucket_mean = {k: (sum(v) / len(v)) if v else 0.0 for k, v in rewards_by_bucket.items()}

        advantages: List[float] = [
            t.reward - bucket_mean[bucket_of(t.role)]
            for t in flat
        ]
        # Global GRPO-style standardisation.
        if len(advantages) >= 2:
            std = statistics.pstdev(advantages) or 1.0
            advantages = [a / std for a in advantages]

        # ------------------------------------------------------------------
        # Build training batch.
        #
        # Tinker RL `Datum` schema (see tinker-docs / quickstart):
        #     Datum(
        #         model_input    = ModelInput.from_ints(prompt_tokens),
        #         loss_fn_inputs = {
        #             "target_tokens": <generated tokens>,
        #             "weights":       <1.0 per generated token>,
        #             "logprobs":      <sampling-time logprobs per generated token>,
        #             "advantages":    <one scalar per generated token, broadcast>,
        #         },
        #     )
        #
        # We do NOT use `renderer.build_supervised_example` — that builds an
        # SFT-style (model_input, weight_mask) tuple, not an RL Datum.
        # Instead we re-tokenise each message history into prompt tokens up
        # to the assistant turn, and use the assistant text as target tokens.
        #
        # This is a simplified path that retokenises after-the-fact rather
        # than capturing logprobs during sampling.  For a proper GRPO loop
        # you would use ``TinkerTokenCompleter`` during rollout to capture
        # logprobs in-flight and avoid this re-tokenisation.  See the
        # cookbook's `rl_basic.py` for the production pattern.
        # ------------------------------------------------------------------
        import numpy as np
        import tinker
        from tinker import types
        from tinker.types import TensorData

        datums: List[Any] = []
        tokenizer = renderer.tokenizer
        for t, adv in zip(flat, advantages):
            if not t.messages or not t.actions:
                continue
            history       = t.messages[:-1] if t.messages[-1].get("role") == "assistant" else t.messages
            final_action  = t.actions[-1] if t.actions else (
                t.messages[-1].get("content", "") if t.messages else ""
            )
            if not final_action:
                continue

            prompt_tokens = renderer.build_generation_prompt(history)
            if hasattr(prompt_tokens, "to_ints"):
                prompt_ids = list(prompt_tokens.to_ints())
            else:
                prompt_ids = list(prompt_tokens)

            completion_ids = tokenizer.encode(final_action, add_special_tokens=False)
            if not completion_ids or not prompt_ids:
                continue

            # Tinker expects:
            #   model_input length == target_tokens length == weights length
            # The standard SFT/RL pattern is to feed all tokens shifted by 1:
            #   tokens   = prompt + completion
            #   input    = tokens[:-1]
            #   target   = tokens[1:]
            #   weights  = [0]*len(prompt) + [1]*len(completion); weights[1:]
            # This way the model is asked to predict the *next* token at every
            # position; the weight mask zeros out positions inside the prompt
            # so only completion tokens contribute to the loss.
            all_tokens   = prompt_ids + completion_ids
            input_ids    = all_tokens[:-1]
            target_ids   = all_tokens[1:]
            mask         = ([0.0] * len(prompt_ids)) + ([1.0] * len(completion_ids))
            mask         = mask[1:]                       # align with target shift
            n            = len(target_ids)

            tt = np.asarray(target_ids, dtype=np.int64)
            mk = np.asarray(mask,       dtype=np.float32)
            # Sampling-time logprobs (zeros for now — see comment above).
            lp = np.zeros(n,                       dtype=np.float32)
            # Advantage broadcast across all completion positions; zero on
            # prompt positions so they don't contribute (mask multiplies in
            # the loss).
            ad = np.asarray(
                [float(adv) if m > 0 else 0.0 for m in mask],
                dtype=np.float32,
            )

            datums.append(types.Datum(
                model_input    = types.ModelInput.from_ints(tokens=input_ids),
                loss_fn_inputs = {
                    # Key names match tinker_cookbook/rl/data_processing.py:
                    # importance_sampling / ppo / cispo expect target_tokens,
                    # logprobs, advantages, and `mask` (NOT `weights` — that's
                    # the SFT key).
                    "target_tokens": TensorData.from_numpy(tt),
                    "logprobs":      TensorData.from_numpy(lp),
                    "advantages":    TensorData.from_numpy(ad),
                    "mask":          TensorData.from_numpy(mk),
                },
            ))

        if not datums:
            log.warning("  no datums produced this step (all trajectories empty?)")
            continue

        # ------------------------------------------------------------------
        # Policy update — Tinker SDK signatures:
        #   forward_backward_async(data, loss_fn, loss_fn_config=None)
        #   optim_step_async(adam_params)  where adam_params is tinker.AdamParams
        # ------------------------------------------------------------------
        fwdbwd_future = await training_client.forward_backward_async(
            datums,
            "importance_sampling",
        )
        optim_future = await training_client.optim_step_async(
            tinker.AdamParams(
                learning_rate = cfg.learning_rate,
                beta1         = 0.9,
                beta2         = 0.95,
                eps           = 1e-8,
            )
        )
        await fwdbwd_future
        await optim_future

        # Metrics.
        mean_util = sum(t.reward     for t in flat) / max(1, len(flat))
        mean_env  = sum(t.env_reward for t in flat) / max(1, len(flat))
        good_count = sum(1 for t in flat if t.role in _GOOD_ROLES)
        evil_count = sum(1 for t in flat if t.role in _EVIL_ROLES)
        good_wins  = sum(1 for t in flat if t.role in _GOOD_ROLES and t.env_reward > 0)
        evil_wins  = sum(1 for t in flat if t.role in _EVIL_ROLES and t.env_reward > 0)
        good_wr = good_wins / good_count if good_count else 0.0
        evil_wr = evil_wins / evil_count if evil_count else 0.0
        log.info(
            f"  trajs={len(flat)}  mean_util={mean_util:+.3f}  mean_env={mean_env:+.2f}  "
            f"good_wr={good_wr:.2%}  evil_wr={evil_wr:.2%}"
        )

        # Periodic checkpoint.
        if (step + 1) % cfg.save_every == 0 or (step + 1) == cfg.steps:
            ckpt_name = f"step_{step+1:05d}"
            save_resp = await training_client.save_weights_for_sampler_async(name=ckpt_name)
            sampler_path = getattr(save_resp, "path", "") or str(save_resp)
            (out_dir / "checkpoints.jsonl").open("a").write(
                json.dumps({
                    "step":         step + 1,
                    "name":         ckpt_name,
                    "sampler_path": str(sampler_path),
                    "mean_util":    mean_util,
                    "good_wr":      good_wr,
                    "evil_wr":      evil_wr,
                }) + "\n"
            )
            log.info(f"  saved {ckpt_name}  →  {sampler_path}")
            log.info(
                f"  evaluate with:  ta.agents.TinkerDistilAgent("
                f"tinker_model_path='{sampler_path}')"
            )

    log.info("Training complete.")


# ===========================================================================
# CLI
# ===========================================================================

def parse_args(argv: Optional[List[str]] = None) -> TrainerConfig:
    p = argparse.ArgumentParser(
        description=(
            "Tinker multi-agent RL training for Avalon "
            "(5-player self-play + optional Reflexion SFT warm-start)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model
    p.add_argument("--base-model",     type=str,   default="meta-llama/Llama-3.2-1B")
    p.add_argument("--lora-rank",      type=int,   default=32)
    p.add_argument("--renderer-name",  type=str,   default="llama3",
                   help="Match base model family: 'llama3' / 'qwen3' / 'role_colon'.")
    p.add_argument("--learning-rate",  type=float, default=2e-5)

    # Rollout
    p.add_argument("--games-per-step", type=int,   default=8)
    p.add_argument("--num-players",    type=int,   default=5)
    p.add_argument("--max-new-tokens", type=int,   default=128)
    p.add_argument("--temperature",    type=float, default=0.9)
    p.add_argument("--env",            type=str,   default="Avalon-v0")
    p.add_argument("--special-roles",  type=str,   default="Merlin,Morgana",
                   help="Comma-separated; 'none' for vanilla.")
    p.add_argument("--cfr-iterations",      type=int, default=50)
    p.add_argument("--cfr-wait-iterations", type=int, default=25)

    # Training
    p.add_argument("--steps",          type=int, default=100)
    p.add_argument("--save-every",     type=int, default=20)

    # SFT
    p.add_argument("--skip-sft",       action="store_true")
    p.add_argument("--sft-epochs",     type=int,   default=1)
    p.add_argument("--sft-lr",         type=float, default=1e-5)

    # Memory / output
    p.add_argument("--memory-path",    type=str, default="results/reflection_memory.json")
    p.add_argument("--cheat-sheet-k",  type=int, default=5)
    p.add_argument("--run-name",       type=str, default=None)
    p.add_argument("--out-dir",        type=str, default="results/tinker_avalon")

    args = p.parse_args(argv)

    sr_raw = args.special_roles.strip()
    sr = None if sr_raw.lower() in ("none", "vanilla", "") else [
        r.strip() for r in sr_raw.split(",") if r.strip()
    ]

    return TrainerConfig(
        base_model           = args.base_model,
        lora_rank            = args.lora_rank,
        renderer_name        = args.renderer_name,
        learning_rate        = args.learning_rate,
        games_per_step       = args.games_per_step,
        num_players          = args.num_players,
        max_new_tokens       = args.max_new_tokens,
        temperature          = args.temperature,
        env_id               = args.env,
        special_roles        = sr,
        cfr_iterations       = args.cfr_iterations,
        cfr_wait_iterations  = args.cfr_wait_iterations,
        steps                = args.steps,
        save_every           = args.save_every,
        skip_sft             = args.skip_sft,
        sft_epochs           = args.sft_epochs,
        sft_lr               = args.sft_lr,
        memory_path          = args.memory_path,
        cheat_sheet_k        = args.cheat_sheet_k,
        run_name             = args.run_name,
        out_dir              = args.out_dir,
    )


def main() -> None:
    cfg = parse_args()
    asyncio.run(rl_train(cfg))


if __name__ == "__main__":
    main()