"""Run multiple TextArena Avalon games in parallel and write one JSON file per game under
``results/multi_play_<timestamp>/game_logs/`` (plus ``summary.json`` in the run folder).

Agent modes
-----------
  --agent deeprole         (default) Five plain DeepRoleAgent players — no GPU required.
  --agent deeprole-llm     Five DeepRoleLLMAgent players backed by a local TRL/HF model.
                           Requires --hf-model (Hub name or local checkpoint path).
  --agent tinker-distil    Five TinkerDistilAgent players backed by a Tinker-hosted LoRA
                           checkpoint (typically one produced by tinker_multiagent.py).
                           Requires --tinker-model (or TINKER_MODEL in .env).

Examples
--------
Plain DeepRole, 20 games, 4 parallel workers:
    python multi_play.py --games 20 --workers 4

DeepRole-LLM with a local TRL checkpoint:
    python multi_play.py --games 8 --agent deeprole-llm \\
        --hf-model /checkpoints/avalon-grpo/checkpoint-500 \\
        --load-in-4bit --skip-llm-mechanical

Tinker-distil evaluation against a trained checkpoint:
    python multi_play.py --games 20 --workers 4 --agent tinker-distil \\
        --tinker-model tinker://UUID:train:0/sampler_weights/step_00020
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_GAME_STATE_RE = re.compile(r"<game_state>\s*(.*?)\s*</game_state>", re.DOTALL | re.IGNORECASE)

_AVALON_SPECIAL_ROLE_NAMES = frozenset(
    {"Servant", "Merlin", "Percival", "Minion", "Morgana", "Mordred", "Oberon"}
)

_AGENT_CHOICES = ("deeprole", "deeprole-llm", "tinker-distil", "openrouter")


def _parse_seat_agents_csv(raw: Optional[str], num_players: int = 5) -> Optional[List[str]]:
    """
    Parse ``--seat-agents`` (e.g. ``"deeprole-llm,deeprole-llm,deeprole-llm,deeprole-llm,tinker-distil"``)
    into a length-``num_players`` list of agent-type strings.  Returns ``None`` if no
    spec is given, in which case the caller should fall back to the
    single ``--agent`` value broadcast to every seat.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) != num_players:
        raise SystemExit(
            f"--seat-agents must list exactly {num_players} entries (one per seat); "
            f"got {len(parts)}: {parts}"
        )
    unknown = [p for p in parts if p not in _AGENT_CHOICES]
    if unknown:
        raise SystemExit(
            f"--seat-agents contains unknown agent type(s) {unknown}. "
            f"Valid: {', '.join(_AGENT_CHOICES)}"
        )
    return parts


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_special_roles_csv(raw: str) -> Optional[List[str]]:
    """Return sorted unique role names, or ``None`` for vanilla (no ``special_roles``)."""
    s = raw.strip()
    if not s or s.lower() in ("none", "vanilla"):
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return None
    unknown = [p for p in parts if p not in _AVALON_SPECIAL_ROLE_NAMES]
    if unknown:
        raise SystemExit(
            f"Unknown role(s) in --special-roles: {unknown}. "
            f"Expected one or more of: {', '.join(sorted(_AVALON_SPECIAL_ROLE_NAMES))}"
        )
    return sorted(set(parts))


def _load_env_file(path: Path) -> None:
    """Set os.environ from KEY=value lines (stdlib only; does not override existing vars)."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


# ---------------------------------------------------------------------------
# Log / game-state helpers
# ---------------------------------------------------------------------------

def extract_game_states_from_log_messages(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in logs:
        msg = entry.get("message", "")
        for m in _GAME_STATE_RE.finditer(msg):
            try:
                out.append(json.loads(m.group(1).strip()))
            except json.JSONDecodeError:
                continue
    return out


def _normalize_votes(votes: Dict[Any, Any]) -> Dict[int, str]:
    return {int(k): str(v).lower() for k, v in votes.items()}


def _vote_passed(votes: Dict[int, str]) -> bool:
    approve_count = sum(1 for v in votes.values() if v == "approve")
    return approve_count > (len(votes) - approve_count)


def extract_avalon_vote_events(game_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    seen_sig: Optional[Tuple[Any, ...]] = None
    for gs in game_states:
        votes_raw = gs.get("votes") or {}
        tp = gs.get("team_proposal") or []
        if len(votes_raw) < 5 or len(tp) == 0:
            continue
        nv = _normalize_votes(votes_raw)
        if len(nv) < 5:
            continue
        sig = (
            int(gs.get("mission_index", 0)),
            tuple(sorted(int(x) for x in tp)),
            tuple(sorted(nv.items())),
        )
        if sig == seen_sig:
            continue
        seen_sig = sig
        approves = sum(1 for v in nv.values() if v == "approve")
        events.append(
            {
                "mission_index": int(gs.get("mission_index", 0)),
                "team_proposal": [int(x) for x in tp],
                "votes": {str(k): v for k, v in sorted(nv.items())},
                "approve_count": approves,
                "reject_count": len(nv) - approves,
                "passed": _vote_passed(nv),
            }
        )
    return events


def _infer_num_players(runs: List[Dict[str, Any]], default: int = 5) -> int:
    for run in runs:
        rw = run.get("rewards") or {}
        if rw:
            return max(int(k) for k in rw.keys()) + 1
    return default


def _reward_value(rw: Dict[str, Any], pid: int) -> Optional[int]:
    val = rw.get(pid) if pid in rw else rw.get(str(pid))
    if val is None:
        return None
    return int(val)


_AVALON_GOOD_ROLES = frozenset({"Servant", "Merlin", "Percival"})
_AVALON_EVIL_ROLES = frozenset({"Minion", "Morgana", "Mordred", "Oberon"})


def _per_game_utility(role: Optional[str], env_reward: Optional[int]) -> Optional[float]:
    if env_reward is None:
        return None
    won = env_reward > 0
    if role in _AVALON_GOOD_ROLES:
        return 0.4 if won else -0.4
    if role in _AVALON_EVIL_ROLES:
        return 0.6 if won else -0.6
    return float(env_reward)


def aggregate_summary_stats(runs: List[Dict[str, Any]], num_players: int = 5) -> Dict[str, Any]:
    n = len(runs)
    num_players = _infer_num_players(runs, default=num_players)
    wins: Dict[int, int] = {pid: 0 for pid in range(num_players)}
    total_utility: Dict[int, float] = {pid: 0.0 for pid in range(num_players)}
    role_wins: Dict[int, Dict[str, int]] = {pid: {} for pid in range(num_players)}
    role_games: Dict[int, Dict[str, int]] = {pid: {} for pid in range(num_players)}
    total_vote_rounds = 0
    proposals_passed = 0
    for run in runs:
        rw = run.get("rewards") or {}
        gi = run.get("game_info") or {}
        for pid in range(num_players):
            val = _reward_value(rw, pid)
            pinfo = gi.get(str(pid))
            if pinfo is None and pid in gi:
                pinfo = gi.get(pid)
            role: Optional[str] = None
            if isinstance(pinfo, dict):
                role = pinfo.get("role")
            if isinstance(role, str):
                role = role or None
            util = _per_game_utility(role, val)
            if util is not None:
                total_utility[pid] += util
            if val is not None and val > 0:
                wins[pid] += 1
            if isinstance(role, str) and role:
                role_wins[pid].setdefault(role, 0)
                role_games[pid].setdefault(role, 0)
                role_games[pid][role] += 1
                if val is not None and val > 0:
                    role_wins[pid][role] += 1
        for ve in run.get("vote_events") or []:
            total_vote_rounds += 1
            if ve.get("passed"):
                proposals_passed += 1

    agent_win_rate_by_role: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for pid in range(num_players):
        by_role: Dict[str, Dict[str, Any]] = {}
        for role in sorted(role_games[pid].keys()):
            g = role_games[pid][role]
            w = role_wins[pid].get(role, 0)
            by_role[role] = {"games": g, "wins": w, "win_rate": (w / g if g else 0.0)}
        agent_win_rate_by_role[str(pid)] = by_role

    # Also compute team-level stats — most useful for Tinker eval where you want
    # to know "did Good or Evil win more often" rather than per-seat win rates.
    team_games = {"good": 0, "evil": 0}
    team_wins  = {"good": 0, "evil": 0}
    for run in runs:
        rw = run.get("rewards") or {}
        gi = run.get("game_info") or {}
        for pid in range(num_players):
            val = _reward_value(rw, pid)
            pinfo = gi.get(str(pid)) if gi.get(str(pid)) is not None else gi.get(pid)
            role  = pinfo.get("role") if isinstance(pinfo, dict) else None
            if not isinstance(role, str):
                continue
            if role in _AVALON_GOOD_ROLES:
                team_games["good"] += 1
                if val is not None and val > 0:
                    team_wins["good"] += 1
            elif role in _AVALON_EVIL_ROLES:
                team_games["evil"] += 1
                if val is not None and val > 0:
                    team_wins["evil"] += 1

    return {
        "agent_wins": {str(pid): wins[pid] for pid in range(num_players)},
        "agent_win_rates": {str(pid): (wins[pid] / n if n else 0.0) for pid in range(num_players)},
        "utility_summary": {
            "note": (
                "Cumulative per-game utility per agent "
                "(Avalon: +0.4 good win, -0.4 good loss, +0.6 bad win, -0.6 bad loss; "
                "raw env reward if role is unknown)."
            ),
            "per_agent_total": {str(pid): total_utility[pid] for pid in range(num_players)},
            "per_agent_mean_per_game": {
                str(pid): (total_utility[pid] / n if n else 0.0) for pid in range(num_players)
            },
        },
        "agent_win_rate_by_role": agent_win_rate_by_role,
        "team_summary": {
            "good_role_seats": team_games["good"],
            "good_role_wins":  team_wins["good"],
            "good_win_rate":   (team_wins["good"] / team_games["good"]) if team_games["good"] else 0.0,
            "evil_role_seats": team_games["evil"],
            "evil_role_wins":  team_wins["evil"],
            "evil_win_rate":   (team_wins["evil"] / team_games["evil"]) if team_games["evil"] else 0.0,
        },
        "voting_summary": {
            "total_vote_rounds": total_vote_rounds,
            "proposals_passed": proposals_passed,
            "proposals_rejected": total_vote_rounds - proposals_passed,
        },
    }


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def _build_one_agent(agent_type: str, payload: Dict[str, Any], ta: Any):
    """Build a single agent instance of the given type, drawing config from payload."""

    if agent_type == "deeprole":
        return ta.agents.DeepRoleAgent()

    if agent_type == "deeprole-llm":
        hf_model = payload.get("hf_model")
        if not hf_model:
            raise ValueError(
                "deeprole-llm seat requires hf_model to be set. "
                "Pass --hf-model on the command line or set HF_MODEL in your environment."
            )
        return ta.agents.DeepRole_LLM(
            model_name_or_path      = hf_model,
            adapter_path            = payload.get("adapter_path") or None,
            device                  = payload.get("device", "auto"),
            load_in_4bit            = bool(payload.get("load_in_4bit", False)),
            load_in_8bit            = bool(payload.get("load_in_8bit", False)),
            max_new_tokens          = int(payload.get("max_new_tokens", 128)),
            temperature             = float(payload.get("temperature", 0.7)),
            fast_deeprole           = True,
            share_llm_backend       = True,   # shared across all deeprole-llm seats
            skip_llm_for_mechanical = bool(payload.get("skip_llm_for_mechanical", True)),
        )

    if agent_type == "tinker-distil":
        tinker_model = payload.get("tinker_model")
        if not tinker_model:
            raise ValueError(
                "tinker-distil seat requires tinker_model to be set. "
                "Pass --tinker-model on the command line or set TINKER_MODEL in .env / environment."
            )
        return ta.agents.TinkerDistilAgent(
            tinker_model_path       = tinker_model,
            max_new_tokens          = int(payload.get("max_new_tokens", 128)),
            temperature             = float(payload.get("temperature", 0.7)),
            fast_deeprole           = True,
            skip_llm_for_mechanical = bool(payload.get("skip_llm_for_mechanical", True)),
        )

    if agent_type == "openrouter":
        openrouter_model = payload.get("openrouter_model")
        if not openrouter_model:
            raise ValueError(
                "openrouter seat requires openrouter_model to be set. "
                "Pass --openrouter-model on the command line or set OPENROUTER_MODEL "
                "in .env / environment."
            )
        # OpenRouterAgent reads OPENROUTER_API_KEY from os.environ on construction.
        # Note: OpenRouterAgent emits raw observation -> raw response (no DeepRole
        # CFR layer); the agent doesn't know game-mechanical actions like
        # <vote>approve</vote>, so it relies entirely on whatever the model
        # produces.  This is a different paradigm from deeprole-llm /
        # tinker-distil, where DeepRole handles all mechanical decisions.
        return ta.agents.OpenRouterAgent(
            model_name = openrouter_model,
            verbose    = bool(payload.get("verbose", False)),
        )

    raise ValueError(f"Unknown agent type {agent_type!r}. Choose from: {_AGENT_CHOICES}")


def _build_agents(payload: Dict[str, Any], ta: Any) -> Dict[int, Any]:
    """
    Construct one agent per seat for one game.

    The payload's ``seat_agents`` field is a list of agent-type strings, one
    per seat (e.g. ``["deeprole-llm", "deeprole-llm", "deeprole-llm",
    "deeprole-llm", "tinker-distil"]``).  All other config fields
    (``hf_model``, ``tinker_model``, etc.) are shared across seats — there's
    only one HF checkpoint per worker process, only one Tinker model URL,
    etc.  If you need different HF models or different Tinker checkpoints
    per seat, you'd extend the payload with per-seat config dicts.

    For ``deeprole-llm`` seats, the underlying ``DeepRoleLLMAgent`` uses
    ``share_llm_backend=True`` so multiple deeprole-llm seats in the same
    worker share one set of model weights.
    """
    seat_agents: List[str] = payload.get("seat_agents") or []
    num_players = payload.get("num_players", 5)

    # Backwards-compatibility: if seat_agents wasn't provided, fall back to
    # the legacy single ``agent`` field broadcast to all seats.
    if not seat_agents:
        agent_type = payload.get("agent", "deeprole")
        seat_agents = [agent_type] * num_players

    if len(seat_agents) != num_players:
        raise ValueError(
            f"seat_agents has {len(seat_agents)} entries but num_players={num_players}; "
            "expected one agent type per seat."
        )

    return {i: _build_one_agent(seat_agents[i], payload, ta) for i in range(num_players)}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _run_one_game(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executed in a worker process. Returns metadata plus paths written."""
    repo_root = Path(payload["repo_root"])
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Worker processes don't inherit the parent's process-level os.environ
    # changes when started by ProcessPoolExecutor with the spawn start method.
    # Re-load .env so TINKER_API_KEY (and friends) are available in the
    # worker's environment for tinker-distil's _TinkerSamplerBackend.
    _load_env_file(repo_root / ".env")

    import textarena as ta  # noqa: WPS433

    run_index = int(payload["run_index"])
    seed      = payload.get("seed")
    env_id    = str(payload["env_id"])
    out_path  = Path(payload["out_path"])

    agents = _build_agents(payload, ta)

    env = ta.make(env_id=env_id)
    special_roles = payload.get("special_roles")
    if special_roles:
        env.reset(num_players=len(agents), special_roles=set(special_roles), seed=seed)
    else:
        env.reset(num_players=len(agents), seed=seed)

    done = False
    while not done:
        player_id, observation = env.get_observation()
        action = agents[player_id](observation)
        done, _step_info = env.step(action=action)

    rewards, game_info = env.close()

    logs = getattr(env.state, "logs", [])
    serializable_logs: List[Dict[str, Any]] = [
        {"from": from_id, "message": message} for from_id, message in logs
    ]

    game_states = extract_game_states_from_log_messages(serializable_logs)
    vote_events = extract_avalon_vote_events(game_states)

    record: Dict[str, Any] = {
        "run_index":    run_index,
        "seed":         seed,
        "env_id":       env_id,
        "agent":        payload.get("agent", "deeprole"),
        "seat_agents":  payload.get("seat_agents") or [payload.get("agent", "deeprole")] * 5,
        "special_roles": sorted(special_roles) if special_roles else None,
        "rewards":      rewards,
        "game_info":    game_info,
        "vote_events":  vote_events,
        "logs":         serializable_logs,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "run_index":    run_index,
        "seed":         seed,
        "out_path":     str(out_path),
        "agent":        payload.get("agent", "deeprole"),
        "rewards":      rewards,
        "game_info":    game_info,
        "special_roles": sorted(special_roles) if special_roles else None,
        "vote_events":  vote_events,
        "ok":           True,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run many TextArena Avalon games in parallel; "
            "save per-game JSON under results/<run>/game_logs/."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # --- game / parallelism ------------------------------------------------
    parser.add_argument("--games",      type=int,  default=4,    help="Number of games to run.")
    parser.add_argument("--workers",    type=int,  default=None, help="Process pool size (default: min(8, games)).")
    parser.add_argument("--seed-base",  type=int,  default=0,    help="Seeds are seed_base + run_index.")
    parser.add_argument("--env",        type=str,  default="Avalon-v0", help="Registered TextArena env id.")
    parser.add_argument(
        "--special-roles", type=str, default="Merlin,Morgana", metavar="ROLES",
        help=(
            "Comma-separated Avalon roles passed to env.reset(special_roles=...). "
            "Use 'none' or 'vanilla' for default 3 Servants / 2 Minions."
        ),
    )
    parser.add_argument("--out-dir", type=str, default=None,
                        help="Output directory (default: <repo>/results/multi_play_<UTC timestamp>).")

    # --- agent selection ---------------------------------------------------
    parser.add_argument(
        "--agent", type=str, default="deeprole", choices=_AGENT_CHOICES,
        help=(
            "All-seats agent type (broadcast to every seat).\n"
            "'deeprole'       — plain DeepRoleAgent, no GPU needed.\n"
            "'deeprole-llm'   — DeepRoleLLMAgent backed by a local TRL/HF model (--hf-model).\n"
            "'tinker-distil'  — TinkerDistilAgent backed by a Tinker-hosted checkpoint "
            "(--tinker-model).\n"
            "Ignored when --seat-agents is given."
        ),
    )
    parser.add_argument(
        "--seat-agents", type=str, default=None, metavar="SEAT0,SEAT1,SEAT2,SEAT3,SEAT4",
        help=(
            "Comma-separated list of 5 agent types — one per seat. Overrides --agent. "
            "Lets you mix agents in one game, e.g. "
            "'deeprole-llm,deeprole-llm,deeprole-llm,deeprole-llm,tinker-distil'. "
            "All seats of a given type share the same model config "
            "(--hf-model is the same for every deeprole-llm seat in a worker, "
            "--tinker-model the same for every tinker-distil seat)."
        ),
    )

    # --- DeepRole-LLM options (only used when --agent deeprole-llm) --------
    llm_group = parser.add_argument_group(
        "DeepRole-LLM options",
        "Only relevant when --agent deeprole-llm.",
    )
    llm_group.add_argument(
        "--hf-model", type=str, default=None, metavar="NAME_OR_PATH",
        help=(
            "HuggingFace Hub name (e.g. 'Qwen/Qwen3-0.6B') or local path to a "
            "TRL-trained checkpoint. Also read from HF_MODEL env var / .env file."
        ),
    )
    llm_group.add_argument(
        "--adapter-path", type=str, default=None, metavar="PATH",
        help="Path to a PEFT/LoRA adapter directory produced by TRL (optional).",
    )
    llm_group.add_argument(
        "--device", type=str, default="auto",
        help="Inference device: 'auto' (GPU if available), 'cuda', or 'cpu'.",
    )
    llm_group.add_argument("--load-in-4bit", action="store_true", help="QLoRA 4-bit quantisation (bitsandbytes).")
    llm_group.add_argument("--load-in-8bit", action="store_true", help="8-bit quantisation (bitsandbytes).")

    # --- Tinker-distil options (only used when --agent tinker-distil) ------
    tinker_group = parser.add_argument_group(
        "Tinker-distil options",
        "Only relevant when --agent tinker-distil.  Requires TINKER_API_KEY in environment.",
    )
    tinker_group.add_argument(
        "--tinker-model", type=str, default=None, metavar="PATH",
        help=(
            "Tinker sampler weight path, e.g. 'tinker://UUID:train:0/sampler_weights/step_00020'. "
            "Also read from TINKER_MODEL env var / .env file."
        ),
    )

    # --- OpenRouter options (only used when --agent openrouter) ------------
    openrouter_group = parser.add_argument_group(
        "OpenRouter options",
        "Only relevant when --agent openrouter.  Requires OPENROUTER_API_KEY in environment.",
    )
    openrouter_group.add_argument(
        "--openrouter-model", type=str, default=None, metavar="MODEL",
        help=(
            "OpenRouter model name, e.g. 'openai/gpt-4o-mini' or "
            "'anthropic/claude-3.5-sonnet'.  Also read from OPENROUTER_MODEL "
            "env var / .env file."
        ),
    )

    # --- shared LLM-call options (used by both deeprole-llm and tinker-distil) ---
    shared_llm = parser.add_argument_group(
        "Shared LLM options",
        "Used by both --agent deeprole-llm and --agent tinker-distil.",
    )
    shared_llm.add_argument("--max-new-tokens", type=int, default=128, help="Max tokens to generate per LLM call.")
    shared_llm.add_argument("--temperature", type=float, default=0.7, help="LLM sampling temperature.")
    shared_llm.add_argument(
        "--skip-llm-mechanical", action="store_true", default=True,
        help=(
            "Skip the LLM on vote/propose/mission turns (DeepRole handles those); "
            "call LLM only on discussion phases. Default: True."
        ),
    )
    shared_llm.add_argument(
        "--no-skip-llm-mechanical", dest="skip_llm_mechanical", action="store_false",
        help="Call the LLM on every turn, including mechanical phases.",
    )

    args = parser.parse_args()

    # Load .env early so we can resolve env-var fallbacks below.
    repo_root = _repo_root()
    _load_env_file(repo_root / ".env")

    # Resolve seat list — explicit --seat-agents overrides --agent.
    seat_agents_list = _parse_seat_agents_csv(args.seat_agents, num_players=5)
    if seat_agents_list is None:
        seat_agents_list = [args.agent] * 5
    seat_types_present = set(seat_agents_list)

    # Validate per-agent-type requirements based on which types are present.
    if "deeprole-llm" in seat_types_present:
        hf_model = args.hf_model or os.getenv("HF_MODEL")
        if not hf_model:
            parser.error(
                "deeprole-llm seat requires --hf-model (or HF_MODEL in .env / environment).\n"
                "Example: --hf-model Qwen/Qwen3-0.6B"
            )
        args.hf_model = hf_model

    if "tinker-distil" in seat_types_present:
        tinker_model = args.tinker_model or os.getenv("TINKER_MODEL")
        if not tinker_model:
            parser.error(
                "tinker-distil seat requires --tinker-model "
                "(or TINKER_MODEL in .env / environment).\n"
                "Example: --tinker-model tinker://UUID:train:0/sampler_weights/step_00020"
            )
        if not os.getenv("TINKER_API_KEY"):
            parser.error(
                "tinker-distil seat requires TINKER_API_KEY to be set in .env or environment."
            )
        args.tinker_model = tinker_model

    if "openrouter" in seat_types_present:
        openrouter_model = args.openrouter_model or os.getenv("OPENROUTER_MODEL")
        if not openrouter_model:
            parser.error(
                "openrouter seat requires --openrouter-model "
                "(or OPENROUTER_MODEL in .env / environment).\n"
                "Example: --openrouter-model openai/gpt-4o-mini"
            )
        if not os.getenv("OPENROUTER_API_KEY"):
            parser.error(
                "openrouter seat requires OPENROUTER_API_KEY to be set in .env or environment."
            )
        args.openrouter_model = openrouter_model

    special_roles_list = _parse_special_roles_csv(args.special_roles)

    games   = max(1, args.games)
    workers = args.workers if args.workers is not None else min(8, games)

    ts      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) if args.out_dir else (repo_root / "results" / f"multi_play_{ts}")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build per-game payloads.
    payloads: List[Dict[str, Any]] = []
    for i in range(games):
        p: Dict[str, Any] = {
            "repo_root":    str(repo_root),
            "run_index":    i,
            "seed":         args.seed_base + i,
            "env_id":       args.env,
            "special_roles": special_roles_list,
            "out_path":     str(out_dir / "game_logs" / f"game_{i:04d}.json"),
            "num_players":  5,
            "seat_agents":  list(seat_agents_list),
            # Legacy ``agent`` field for record-keeping in per-game JSONs;
            # set to "mixed" if seats are heterogeneous, else the single type.
            "agent":        seat_agents_list[0]
                            if len(seat_types_present) == 1
                            else "mixed",
        }
        # Attach config relevant to whichever seat types are present.
        if "deeprole-llm" in seat_types_present:
            p.update(
                hf_model               = args.hf_model,
                adapter_path           = args.adapter_path,
                device                 = args.device,
                load_in_4bit           = args.load_in_4bit,
                load_in_8bit           = args.load_in_8bit,
            )
        if "tinker-distil" in seat_types_present:
            p.update(
                tinker_model           = args.tinker_model,
            )
        if "openrouter" in seat_types_present:
            p.update(
                openrouter_model       = args.openrouter_model,
            )
        # Shared LLM-call options apply to any LLM-backed seat.
        if {"deeprole-llm", "tinker-distil"} & seat_types_present:
            p.update(
                max_new_tokens         = args.max_new_tokens,
                temperature            = args.temperature,
                skip_llm_for_mechanical= args.skip_llm_mechanical,
            )
        payloads.append(p)

    # Run games — tolerate per-game failures so one crash doesn't kill 1000 games.
    # Common causes: a worker raises during an LLM API call (rate limit,
    # transient network error, OpenAI SDK version mismatch when decoding a
    # non-200 response, etc.); the env raises on a malformed action that the
    # game state parser can't handle.  Either way we log the failure with the
    # run_index so it can be reproduced and continue with the rest.
    summary: List[Dict[str, Any]] = []
    failed:  List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        # Pair each future with its payload so we can identify which game
        # crashed even when the worker dies before returning anything.
        future_to_idx = {
            ex.submit(_run_one_game, p): i
            for i, p in enumerate(payloads)
        }
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                summary.append(fut.result())
            except Exception as exc:
                failed.append({
                    "run_index": idx,
                    "seed":      payloads[idx].get("seed"),
                    "error":     f"{type(exc).__name__}: {exc}",
                })
                print(
                    f"[multi_play] game {idx} failed: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

    summary.sort(key=lambda x: x["run_index"])
    if failed:
        print(
            f"[multi_play] {len(failed)} of {len(payloads)} games failed; "
            f"continuing with {len(summary)} successful games.",
            flush=True,
        )

    # Write manifest.
    manifest_path = out_dir / "summary.json"

    # Compose a human-readable agent description.
    if len(seat_types_present) == 1:
        only = next(iter(seat_types_present))
        if only == "deeprole-llm":
            agent_desc = f"DeepRole_LLM x5 (model={args.hf_model})"
        elif only == "tinker-distil":
            agent_desc = f"TinkerDistilAgent x5 (model={args.tinker_model})"
        elif only == "openrouter":
            agent_desc = f"OpenRouterAgent x5 (model={args.openrouter_model})"
        else:
            agent_desc = "DeepRoleAgent x5"
        legacy_agent_field = only
    else:
        # Build a compact "x4 deeprole-llm + x1 tinker-distil" style description.
        from collections import Counter
        counts = Counter(seat_agents_list)
        parts = [f"x{n} {name}" for name, n in counts.most_common()]
        agent_desc = " + ".join(parts)
        legacy_agent_field = "mixed"

    manifest: Dict[str, Any] = {
        "created_utc":  ts,
        "repo_root":    str(repo_root),
        "env_id":       args.env,
        "special_roles": special_roles_list,
        "agent":        legacy_agent_field,
        "agent_desc":   agent_desc,
        "seat_agents":  seat_agents_list,
        "games":        games,
        "workers":      workers,
        "seed_base":    args.seed_base,
    }
    if "deeprole-llm" in seat_types_present:
        manifest["llm_config"] = {
            "hf_model":               args.hf_model,
            "adapter_path":           args.adapter_path,
            "device":                 args.device,
            "load_in_4bit":           args.load_in_4bit,
            "load_in_8bit":           args.load_in_8bit,
            "max_new_tokens":         args.max_new_tokens,
            "temperature":            args.temperature,
            "skip_llm_for_mechanical": args.skip_llm_mechanical,
        }
    if "tinker-distil" in seat_types_present:
        manifest["tinker_config"] = {
            "tinker_model":           args.tinker_model,
            "max_new_tokens":         args.max_new_tokens,
            "temperature":            args.temperature,
            "skip_llm_for_mechanical": args.skip_llm_mechanical,
        }
    if "openrouter" in seat_types_present:
        manifest["openrouter_config"] = {
            "openrouter_model":       args.openrouter_model,
        }
    manifest.update(aggregate_summary_stats(summary))
    manifest["runs"] = summary
    if failed:
        manifest["failed_games"] = failed
        manifest["games_succeeded"] = len(summary)
        manifest["games_failed"]    = len(failed)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print a concise headline so the user knows immediately how the run went.
    team = manifest.get("team_summary", {})
    print(
        f"Wrote {games} game JSON files under:\n  {out_dir / 'game_logs'}\n"
        f"and summary:\n  {manifest_path}\n"
        f"\n"
        f"Seats:    {' | '.join(f'P{i}={t}' for i, t in enumerate(seat_agents_list))}\n"
        f"Headline: {agent_desc}  good_wr={team.get('good_win_rate', 0):.2%}  "
        f"evil_wr={team.get('evil_win_rate', 0):.2%}"
    )


if __name__ == "__main__":
    main()