"""Run multiple TextArena Avalon games in parallel and write one JSON file per game under
``results/multi_play_<timestamp>/game_logs/`` (plus ``summary.json`` in the run folder).

Agent modes
-----------
  --agent deeprole        (default) Five plain DeepRoleAgent players — no GPU required.
  --agent deeprole-llm    Five DeepRoleLLMAgent players backed by a local TRL/HF model.
                          Requires --hf-model (Hub name or local checkpoint path).

Example — plain DeepRole, 20 games, 4 parallel workers:
    python multi_play.py --games 20 --workers 4

Example — DeepRole-LLM with a TRL checkpoint:
    python multi_play.py --games 8 --agent deeprole-llm \\
        --hf-model /checkpoints/avalon-grpo/checkpoint-500 \\
        --load-in-4bit --skip-llm-mechanical

Example — DeepRole-LLM with a LoRA adapter:
    python multi_play.py --games 4 --agent deeprole-llm \\
        --hf-model meta-llama/Llama-3.2-1B \\
        --adapter-path /checkpoints/avalon-lora \\
        --device cuda
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

_AGENT_CHOICES = ("deeprole", "deeprole-llm")


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
# Log / game-state helpers (unchanged)
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
        "voting_summary": {
            "total_vote_rounds": total_vote_rounds,
            "proposals_passed": proposals_passed,
            "proposals_rejected": total_vote_rounds - proposals_passed,
        },
    }


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def _build_agents(payload: Dict[str, Any], ta: Any) -> Dict[int, Any]:
    """
    Construct the five agents for one game worker process.

    For ``deeprole-llm``, all five share one loaded model instance via
    ``share_llm_backend=True`` (avoids loading weights 5× per process).
    """
    agent_type = payload.get("agent", "deeprole")
    num_players = payload.get("num_players", 5)

    if agent_type == "deeprole":
        return {i: ta.agents.DeepRoleAgent() for i in range(num_players)}

    if agent_type == "deeprole-llm":
        hf_model = payload.get("hf_model")
        if not hf_model:
            raise ValueError(
                "agent='deeprole-llm' requires hf_model to be set. "
                "Pass --hf-model on the command line or set HF_MODEL in your environment."
            )
        llm_kwargs: Dict[str, Any] = dict(
            model_name_or_path      = hf_model,
            adapter_path            = payload.get("adapter_path") or None,
            device                  = payload.get("device", "auto"),
            load_in_4bit            = bool(payload.get("load_in_4bit", False)),
            load_in_8bit            = bool(payload.get("load_in_8bit", False)),
            max_new_tokens          = int(payload.get("max_new_tokens", 128)),
            temperature             = float(payload.get("temperature", 0.7)),
            fast_deeprole           = True,
            share_llm_backend       = True,   # one model instance per worker process
            skip_llm_for_mechanical = bool(payload.get("skip_llm_for_mechanical", True)),
        )
        return {i: ta.agents.DeepRole_LLM(**llm_kwargs) for i in range(num_players)}

    raise ValueError(f"Unknown agent type {agent_type!r}. Choose from: {_AGENT_CHOICES}")


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _run_one_game(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executed in a worker process. Returns metadata plus paths written."""
    repo_root = Path(payload["repo_root"])
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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
            "'deeprole' — plain DeepRoleAgent, no GPU needed. "
            "'deeprole-llm' — DeepRoleLLMAgent backed by a local TRL/HF model (requires --hf-model)."
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
    llm_group.add_argument("--max-new-tokens", type=int, default=128, help="Max tokens to generate per LLM call.")
    llm_group.add_argument("--temperature", type=float, default=0.7, help="LLM sampling temperature.")
    llm_group.add_argument(
        "--skip-llm-mechanical", action="store_true", default=True,
        help=(
            "Skip the LLM on vote/propose/mission turns (DeepRole handles those); "
            "call LLM only on discussion phases. Default: True — saves GPU compute."
        ),
    )
    llm_group.add_argument(
        "--no-skip-llm-mechanical", dest="skip_llm_mechanical", action="store_false",
        help="Call the LLM on every turn, including mechanical phases.",
    )

    args = parser.parse_args()

    # Validate deeprole-llm requirements early
    if args.agent == "deeprole-llm":
        hf_model = args.hf_model or os.getenv("HF_MODEL")
        if not hf_model:
            repo_root_env = _repo_root()
            _load_env_file(repo_root_env / ".env")
            hf_model = os.getenv("HF_MODEL")
        if not hf_model:
            parser.error(
                "--agent deeprole-llm requires --hf-model (or HF_MODEL in .env / environment).\n"
                "Example: --hf-model Qwen/Qwen3-0.6B"
            )
        args.hf_model = hf_model   # normalise so payload always has it

    special_roles_list = _parse_special_roles_csv(args.special_roles)
    repo_root = _repo_root()
    _load_env_file(repo_root / ".env")

    games   = max(1, args.games)
    workers = args.workers if args.workers is not None else min(8, games)

    ts      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) if args.out_dir else (repo_root / "results" / f"multi_play_{ts}")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build per-game payloads
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
            "agent":        args.agent,
        }
        # Attach LLM settings (ignored by worker when agent == "deeprole")
        if args.agent == "deeprole-llm":
            p.update(
                hf_model               = args.hf_model,
                adapter_path           = args.adapter_path,
                device                 = args.device,
                load_in_4bit           = args.load_in_4bit,
                load_in_8bit           = args.load_in_8bit,
                max_new_tokens         = args.max_new_tokens,
                temperature            = args.temperature,
                skip_llm_for_mechanical= args.skip_llm_mechanical,
            )
        payloads.append(p)

    # Run games
    summary: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run_one_game, p) for p in payloads]
        for fut in as_completed(futures):
            summary.append(fut.result())

    summary.sort(key=lambda x: x["run_index"])

    # Write manifest
    manifest_path = out_dir / "summary.json"
    agent_desc = (
        f"DeepRole_LLM x5 (model={args.hf_model})"
        if args.agent == "deeprole-llm"
        else "DeepRoleAgent x5"
    )
    manifest: Dict[str, Any] = {
        "created_utc":  ts,
        "repo_root":    str(repo_root),
        "env_id":       args.env,
        "special_roles": special_roles_list,
        "agent":        args.agent,
        "agent_desc":   agent_desc,
        "games":        games,
        "workers":      workers,
        "seed_base":    args.seed_base,
    }
    if args.agent == "deeprole-llm":
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
    manifest.update(aggregate_summary_stats(summary))
    manifest["runs"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"Wrote {games} game JSON files under:\n  {out_dir / 'game_logs'}\n"
        f"and summary:\n  {manifest_path}"
    )


if __name__ == "__main__":
    main()