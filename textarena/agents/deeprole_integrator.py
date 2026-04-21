"""
DeepRole ↔ TextArena Avalon bridge (stdlib only).

Runs the native ``deeprole`` CFR binary from the DeepRole checkout, keeps the
CFR search tree in sync with TextArena ``<game_state>`` JSON snapshots, and
emits Avalon XML tags for mechanical phases.

Tree descent follows ``battlefield/bots/deeprole/bot.py`` (``Deeprole.handle_transition``).
Lookup tables match ``battlefield/bots/deeprole/lookup_tables.py``.

**Uncertain / heuristic areas** (called out inline):
  * Fifth consecutive rejected proposal auto-approves without a vote in TextArena;
    we descend the vote branch with an all-approve bit pattern as a stand-in.
  * ``num_fails`` for the mission edge is inferred from public counters / mission
    actions and may differ from true shuffled fail-card counts in edge rulesets.
  * Perspective index uses the MAP-est assignment consistent with the player's
    TextArena role mapped into DeepRole's {merlin, assassin, minion, servant}.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Embedded lookup tables (DeepRole lookup_tables.py — must stay in sync)
# ---------------------------------------------------------------------------

ASSIGNMENT_TO_VIEWPOINT: List[List[int]] = [
    [1, 8, 12, 0, 0],
    [2, 9, 0, 12, 0],
    [3, 10, 0, 0, 12],
    [1, 12, 8, 0, 0],
    [4, 0, 9, 13, 0],
    [5, 0, 10, 0, 13],
    [2, 13, 0, 8, 0],
    [4, 0, 13, 9, 0],
    [6, 0, 0, 10, 14],
    [3, 14, 0, 0, 8],
    [5, 0, 14, 0, 9],
    [6, 0, 0, 14, 10],
    [8, 1, 11, 0, 0],
    [9, 2, 0, 11, 0],
    [10, 3, 0, 0, 11],
    [12, 1, 7, 0, 0],
    [0, 4, 9, 13, 0],
    [0, 5, 10, 0, 13],
    [13, 2, 0, 7, 0],
    [0, 4, 13, 9, 0],
    [0, 6, 0, 10, 14],
    [14, 3, 0, 0, 7],
    [0, 5, 14, 0, 9],
    [0, 6, 0, 14, 10],
    [7, 11, 1, 0, 0],
    [9, 0, 2, 11, 0],
    [10, 0, 3, 0, 11],
    [11, 7, 1, 0, 0],
    [0, 9, 4, 12, 0],
    [0, 10, 5, 0, 12],
    [13, 0, 2, 7, 0],
    [0, 13, 4, 8, 0],
    [0, 0, 6, 10, 14],
    [14, 0, 3, 0, 7],
    [0, 14, 5, 0, 8],
    [0, 0, 6, 14, 10],
    [7, 11, 0, 1, 0],
    [8, 0, 11, 2, 0],
    [10, 0, 0, 3, 11],
    [11, 7, 0, 1, 0],
    [0, 8, 12, 4, 0],
    [0, 10, 0, 5, 12],
    [12, 0, 7, 2, 0],
    [0, 12, 8, 4, 0],
    [0, 0, 10, 6, 13],
    [14, 0, 0, 3, 7],
    [0, 14, 0, 5, 8],
    [0, 0, 14, 6, 9],
    [7, 11, 0, 0, 1],
    [8, 0, 11, 0, 2],
    [9, 0, 0, 11, 3],
    [11, 7, 0, 0, 1],
    [0, 8, 12, 0, 4],
    [0, 9, 0, 12, 5],
    [12, 0, 7, 0, 2],
    [0, 12, 8, 0, 4],
    [0, 0, 9, 13, 6],
    [13, 0, 0, 7, 3],
    [0, 13, 0, 8, 5],
    [0, 0, 13, 9, 6],
]

_DEEPROLE_EVIL = frozenset({"assassin", "minion"})

# Mission team sizes (Avalon env.py — duplicated to avoid importing textarena)
_TEAM_SIZES: Dict[int, List[int]] = {
    5: [2, 3, 2, 3, 3],
    6: [2, 3, 4, 3, 4],
    7: [2, 3, 3, 4, 4],
    8: [3, 4, 4, 5, 5],
    9: [3, 4, 4, 5, 5],
    10: [3, 4, 4, 5, 5],
}

_DISCUSSION_FALLBACKS = (
    "I'll watch how the next votes go before committing.",
    "Still weighing who looks trustworthy on this mission.",
    "Let's hear a bit more before we lock a team.",
    "I don't have a strong read yet—open to arguments.",
)

# ---------------------------------------------------------------------------
# Module-level caches (one-time init wrappers)
# ---------------------------------------------------------------------------

_assignment_view_cache: Optional[List[List[int]]] = None
_hidden_tables_cache: Optional[Tuple[Dict[Tuple[str, ...], int], List[Tuple[str, ...]]]] = None
_deeprole_path_cache: Dict[str, Tuple[str, str]] = {}


def get_cached_assignment_viewpoint() -> List[List[int]]:
    global _assignment_view_cache
    if _assignment_view_cache is None:
        _assignment_view_cache = [row[:] for row in ASSIGNMENT_TO_VIEWPOINT]
    return _assignment_view_cache


def build_hidden_state_tables() -> Tuple[Dict[Tuple[str, ...], int], List[Tuple[str, ...]]]:
    """
    Build ``hidden_state_to_assignment_id`` and ``assignment_id_to_hidden_state``
    exactly like DeepRole ``lookup_tables.py`` (ordered triples Merlin/Assassin/Minion).
    """
    global _hidden_tables_cache
    if _hidden_tables_cache is None:
        h2i: Dict[Tuple[str, ...], int] = {}
        i2h: List[Tuple[str, ...]] = []
        for i, (merlin, assassin, minion) in enumerate(itertools.permutations(range(5), 3)):
            hidden = ["servant"] * 5
            hidden[merlin] = "merlin"
            hidden[assassin] = "assassin"
            hidden[minion] = "minion"
            tup = tuple(hidden)
            h2i[tup] = i
            i2h.append(tup)
        _hidden_tables_cache = (h2i, i2h)
    return _hidden_tables_cache


def get_cached_hidden_state_tables() -> Tuple[Dict[Tuple[str, ...], int], List[Tuple[str, ...]]]:
    return build_hidden_state_tables()


# ---------------------------------------------------------------------------
# Binary discovery & subprocess runner
# ---------------------------------------------------------------------------


def dr_find_deeprole_binary_and_cwd(binary: str = "deeprole") -> Tuple[str, str]:
    """
    Locate ``.../bots/deeprole/deeprole/code/<binary>`` and the cwd DeepRole uses
    (inner ``deeprole`` bundle directory — same as ``run_deeprole.py``).
    """
    env_cwd = os.environ.get("DEEPROLE_PLAY_CWD")
    env_bin = os.environ.get("DEEPROLE_BINARY")
    if env_cwd and env_bin:
        return str(Path(env_bin).resolve()), str(Path(env_cwd).resolve())

    env_root = (
        os.environ.get("TEXTARENA_DEEPROLE_ROOT")
        or os.environ.get("TEXTARENA_DEEPTROLE_ROOT")
        or os.environ.get("DEEPROLE_REPO")
        or os.environ.get("DEEPROLE_ROOT")
        or os.environ.get("DEEPTROLE_ROOT")
    )
    search_roots: List[Path] = []
    if env_root:
        search_roots.append(Path(env_root).resolve())
    search_roots.append(Path.cwd().resolve())
    here = Path(__file__).resolve()
    search_roots.extend(here.parents)

    rel_suffix = Path("DeepRole") / "battlefield" / "battlefield" / "bots" / "deeprole" / "deeprole" / "code" / binary
    for root in search_roots:
        candidate = (root / rel_suffix).resolve()
        if candidate.is_file():
            cwd = str(candidate.parent.parent)
            return str(candidate), cwd
    alt2 = Path("deeprole") / "code" / binary
    for root in search_roots:
        candidate = (root / alt2).resolve()
        if candidate.is_file():
            return str(candidate), str(candidate.parent.parent)
    # Shorter layout: repo root already at battlefield/battlefield/...
    alt = Path("battlefield") / "battlefield" / "bots" / "deeprole" / "deeprole" / "code" / binary
    for root in search_roots:
        candidate = (root / alt).resolve()
        if candidate.is_file():
            return str(candidate), str(candidate.parent.parent)
    return binary, str(Path.cwd())


def get_cached_deeprole_paths(binary: str = "deeprole") -> Tuple[str, str]:
    if binary not in _deeprole_path_cache:
        _deeprole_path_cache[binary] = dr_find_deeprole_binary_and_cwd(binary)
    return _deeprole_path_cache[binary]


_drun_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}


def dr_run_deeprole_on_node(
    node: Dict[str, Any],
    iterations: int,
    wait_iterations: int,
    *,
    no_zero: bool,
    nn_folder: str,
    binary: str,
) -> Dict[str, Any]:
    """
    Invoke ``deeprole --play`` with belief on stdin; parse JSON stdout.
    Mirrors ``actually_run_deeprole_on_node`` + small LRU-ish cache.
    """
    global _drun_cache
    if len(_drun_cache) > 250:
        _drun_cache.clear()

    belief_key = tuple(node["new_belief"]) if isinstance(node["new_belief"], list) else tuple(node["new_belief"])
    cache_key = (
        node["proposer"],
        node["succeeds"],
        node["fails"],
        node["propose_count"],
        belief_key,
        iterations,
        wait_iterations,
        no_zero,
        nn_folder,
        binary,
    )
    if cache_key in _drun_cache:
        return dict(_drun_cache[cache_key])

    exe, cwd = get_cached_deeprole_paths(binary)
    cmd = [
        exe,
        "--play",
        f"--proposer={node['proposer']}",
        f"--succeeds={node['succeeds']}",
        f"--fails={node['fails']}",
        f"--propose_count={node['propose_count']}",
        "--depth=1",
        f"--iterations={iterations}",
        f"--witers={wait_iterations}",
        f"--modeldir={nn_folder}",
    ]
    if no_zero:
        belief = node["nozero_belief"]
    else:
        belief = node["new_belief"]
    payload = str(list(belief)) + "\n"

    try:
        proc = subprocess.run(
            cmd,
            input=payload.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            check=False,
        )
    except OSError:
        return {}

    if proc.returncode != 0:
        return {}

    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

    _drun_cache[cache_key] = dict(out)
    return dict(out)


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------


def dr_normalize_observation(observation: Any) -> str:
    if isinstance(observation, str):
        return observation
    if isinstance(observation, (list, tuple)):
        parts: List[str] = []
        for chunk in observation:
            if isinstance(chunk, str):
                parts.append(chunk)
            else:
                parts.append(str(chunk))
        return "\n".join(parts)
    return str(observation)


def dr_parse_game_states(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    low = text.lower()
    token_open = "<game_state>"
    token_close = "</game_state>"
    idx = 0
    while True:
        a = low.find(token_open, idx)
        if a < 0:
            break
        start = a + len(token_open)
        b = low.find(token_close, start)
        if b < 0:
            break
        raw = text[start:b].strip()
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            pass
        idx = b + len(token_close)
    return out


def dr_phase_str(game_state: Dict[str, Any]) -> str:
    ph = game_state.get("phase")
    if ph is None:
        return "unknown"
    if isinstance(ph, str):
        return ph
    return str(ph)


# ---------------------------------------------------------------------------
# Bit helpers (DeepRole cfr_bot.py)
# ---------------------------------------------------------------------------


def proposal_to_bitstring(proposal: List[int]) -> int:
    result = 0
    for p in proposal:
        result |= 1 << int(p)
    assert result < 32
    return result


def bitstring_to_proposal(bitstring: int) -> Tuple[int, ...]:
    res: List[int] = []
    for i in range(5):
        if (1 << i) & bitstring:
            res.append(i)
    assert len(res) in (2, 3)
    return tuple(res)


def votes_to_bitstring(votes: Dict[int, str], num_players: int) -> int:
    result = 0
    for i in range(num_players):
        v = votes.get(i, "reject")
        if str(v).lower() == "approve":
            result |= 1 << i
    return result


def get_start_node(proposer: int) -> Dict[str, Any]:
    u = 1.0 / 60.0
    belief = [u] * 60
    return {
        "type": "TERMINAL_PROPOSE_NN",
        "succeeds": 0,
        "fails": 0,
        "propose_count": 0,
        "proposer": int(proposer),
        "new_belief": list(belief),
        "nozero_belief": list(belief),
    }


# ---------------------------------------------------------------------------
# Role / model helpers
# ---------------------------------------------------------------------------


def _ta_role_to_dr(ta_role: str) -> str:
    name = str(ta_role).strip()
    if name == "Merlin":
        return "merlin"
    if name in ("Servant", "Percival"):
        return "servant"
    if name in ("Minion", "Morgana", "Mordred", "Oberon"):
        return "minion"  # both evil slots acceptable in consistency check
    return "servant"


def _assignment_matches_ta(hid: Tuple[str, ...], pid: int, dr_expect: str) -> bool:
    r = hid[pid]
    if dr_expect == "merlin":
        return r == "merlin"
    if dr_expect == "servant":
        return r == "servant"
    if dr_expect == "minion":
        return r in _DEEPROLE_EVIL
    return False


def _map_perspective(player: int, ta_role: str, belief: List[float]) -> int:
    _, id_to_hid = build_hidden_state_tables()
    dr = _ta_role_to_dr(ta_role)
    best_aid = -1
    best_p = -1.0
    for aid, prob in enumerate(belief):
        if prob > best_p and _assignment_matches_ta(id_to_hid[aid], player, dr):
            best_p = prob
            best_aid = aid
    if best_aid < 0:
        for aid, hid in enumerate(id_to_hid):
            if _assignment_matches_ta(hid, player, dr):
                best_aid = aid
                break
    if best_aid < 0:
        return 0
    return int(ASSIGNMENT_TO_VIEWPOINT[best_aid][player])


def _team_size(num_players: int, mission_index: int) -> int:
    row = _TEAM_SIZES.get(int(num_players))
    if not row or not (0 <= mission_index < len(row)):
        return 2
    return int(row[mission_index])


def _nn_dir_has_prefix3(cwd: str, nn_folder: str) -> bool:
    base = Path(cwd) / nn_folder
    if not base.is_dir():
        return False
    try:
        for p in base.iterdir():
            if p.is_file() and p.name.startswith("3_"):
                return True
    except OSError:
        return False
    return False


def _should_skip_deeprole(gs: Dict[str, Any], cwd: str, nn_folder: str) -> bool:
    phase = dr_phase_str(gs)
    if phase.lower().replace("_", "-") in ("guess-merlin", "guess merlin"):
        return True
    if phase == "Guess-Merlin":
        return True
    ms = int(gs.get("mission_successes", 0) or 0)
    if ms >= 3 and not _nn_dir_has_prefix3(cwd, nn_folder):
        return True
    return False


def _parse_last_tag_json(text: str, tag: str) -> Optional[Dict[str, Any]]:
    open_t = f"<{tag}>"
    close_t = f"</{tag}>"
    low = text.lower()
    lo = open_t.lower()
    lc = close_t.lower()
    idx = 0
    last: Optional[Dict[str, Any]] = None
    while True:
        a = low.find(lo, idx)
        if a < 0:
            break
        start = a + len(lo)
        b = low.find(lc, start)
        if b < 0:
            break
        raw = text[start:b].strip()
        try:
            last = json.loads(raw)
        except json.JSONDecodeError:
            last = None
        idx = b + len(lc)
    return last


def _sample_index(probs: List[float]) -> int:
    s = sum(max(0.0, float(p)) for p in probs)
    if s <= 0:
        return random.randrange(len(probs))
    r = random.random() * s
    acc = 0.0
    for i, p in enumerate(probs):
        acc += max(0.0, float(p))
        if r <= acc:
            return i
    return len(probs) - 1


# ---------------------------------------------------------------------------
# DeepRoleIntegrator
# ---------------------------------------------------------------------------


class _SyncState:
    """Tracks how many ``<game_state>`` snapshots are already woven into the CFR tree."""

    __slots__ = ("snap_cursor",)

    def __init__(self, snap_cursor: int = -1) -> None:
        self.snap_cursor = snap_cursor


class DeepRoleIntegrator:
    """
    Stateful DeepRole player for TextArena Avalon observations.

    Public attributes (mirrored by ``_InstrumentedDeepRoleIntegrator`` in
    ``deeprole_llm.py`` via subclassing): ``_belief``, ``_perspective``, ``_node``,
    ``_player``, ``_role`` — all updated each ``__call__``.
    """

    def __init__(
        self,
        nn_folder: str = "deeprole_zeroing_winprobs",
        binary: str = "deeprole",
        no_zero: bool = False,
        iterations: Optional[int] = None,
        wait_iterations: Optional[int] = None,
    ) -> None:
        self.nn_folder = nn_folder
        self.binary = binary
        self.no_zero = bool(no_zero)
        self.iterations = int(iterations) if iterations is not None else 100
        self.wait_iterations = int(wait_iterations) if wait_iterations is not None else 50

        self._node: Dict[str, Any] = {}
        self._belief: List[float] = [1.0 / 60.0] * 60
        self._perspective = 0
        self._player = 0
        self._role = "servant"

        self._sync = _SyncState(snap_cursor=-1)
        self._exe_ok: Optional[bool] = None

    # -- public façade -----------------------------------------------------

    def __call__(self, observation: Any) -> str:
        text = dr_normalize_observation(observation)
        ps = _parse_last_tag_json(text, "player_state")
        if ps is not None:
            self._player = int(ps.get("pid", self._player))
            self._role = _ta_role_to_dr(str(ps.get("role", "Servant")))
        ta_role_for_view = str(ps.get("role", "Servant")) if ps else "Servant"

        snaps = dr_parse_game_states(text)
        if not snaps:
            return random.choice(_DISCUSSION_FALLBACKS)

        # Observation buffer was cleared / rewound (new match or truncated history).
        if self._sync.snap_cursor >= len(snaps):
            self._full_reset()

        if not self._node:
            self._bootstrap(snaps[0])

        while self._sync.snap_cursor < len(snaps) - 1:
            old = snaps[self._sync.snap_cursor]
            new = snaps[self._sync.snap_cursor + 1]
            self._apply_transition(old, new)
            self._sync.snap_cursor += 1

        gs = snaps[-1]
        self._belief = list(self._node.get("new_belief", self._belief))
        self._perspective = _map_perspective(self._player, ta_role_for_view, self._belief)

        exe, cwd = get_cached_deeprole_paths(self.binary)
        self._exe_ok = Path(exe).is_file() if exe != self.binary else False
        skip_dr = _should_skip_deeprole(gs, cwd, self.nn_folder) or not self._exe_ok

        n_players = int(gs.get("num_players", 5))
        if n_players != 5:
            return self._fallback_mechanical(gs, dr_phase_str(gs))

        phase = dr_phase_str(gs)
        ph_l = phase.lower().replace("_", "-")

        if ph_l in ("guess-merlin", "guess merlin") or phase == "Guess-Merlin":
            return self._fallback_guess_merlin(gs)

        if skip_dr:
            return self._fallback_mechanical(gs, phase)

        if ph_l in ("discussion",):
            return random.choice(_DISCUSSION_FALLBACKS)

        if ph_l in ("team-proposal", "team proposal"):
            if int(gs.get("leader_pid", -1)) != self._player:
                return random.choice(_DISCUSSION_FALLBACKS)
            return self._act_propose(gs)

        if ph_l in ("voting",):
            return self._act_vote(gs)

        if ph_l in ("mission",):
            team = gs.get("team_proposal") or []
            if self._player not in team:
                return random.choice(_DISCUSSION_FALLBACKS)
            return self._act_mission(gs)

        return random.choice(_DISCUSSION_FALLBACKS)

    # -- lifecycle ---------------------------------------------------------

    def _full_reset(self) -> None:
        self._node = {}
        self._belief = [1.0 / 60.0] * 60
        self._sync.snap_cursor = -1

    def _bootstrap(self, snap: Dict[str, Any]) -> None:
        leader = int(snap.get("leader_pid", 0))
        start = get_start_node(leader)
        exe, cwd = get_cached_deeprole_paths(self.binary)
        self._exe_ok = Path(exe).is_file() if exe != self.binary else False
        if not _should_skip_deeprole(snap, cwd, self.nn_folder) and self._exe_ok:
            self._node = dr_run_deeprole_on_node(
                start,
                self.iterations,
                self.wait_iterations,
                no_zero=self.no_zero,
                nn_folder=self.nn_folder,
                binary=self.binary,
            )
            if not self._node:
                self._node = start
        else:
            self._node = start
        self._belief = list(self._node.get("new_belief", self._belief))
        self._sync.snap_cursor = 0

    # -- tree descent (cf. Deeprole.handle_transition) -------------------

    def _apply_transition(self, old_gs: Dict[str, Any], new_gs: Dict[str, Any]) -> None:
        if self._node.get("type") == "TERMINAL_MERLIN" or old_gs.get("phase") == "Guess-Merlin":
            return

        old_p = dr_phase_str(old_gs)
        new_p = dr_phase_str(new_gs)
        ol = old_p.lower().replace("_", "-")
        nl = new_p.lower().replace("_", "-")
        n_play = int(old_gs.get("num_players", new_gs.get("num_players", 5)))

        if self._node.get("type") == "TERMINAL_PROPOSE_NN":
            self._expand_nn_terminal()

        if ol in ("team-proposal", "team proposal") and nl in ("voting",):
            team = new_gs.get("team_proposal") or old_gs.get("team_proposal") or []
            self._descend_propose(team)

        elif ol in ("voting",) and nl in ("mission", "discussion"):
            votes = old_gs.get("votes") or new_gs.get("votes") or {}
            if len(votes) < n_play:
                votes = new_gs.get("votes") or votes
            self._descend_vote(votes, n_play)

        elif ol in ("team-proposal", "team proposal") and nl in ("mission",):
            # UNCERTAIN: fifth proposal auto-approved — synthetic unanimous approve.
            fake_votes = {i: "approve" for i in range(n_play)}
            self._descend_propose(new_gs.get("team_proposal") or old_gs.get("team_proposal") or [])
            self._descend_vote(fake_votes, n_play)

        elif ol in ("mission",) and nl in ("discussion", "guess-merlin", "guess merlin"):
            nf = self._infer_num_fails(old_gs, new_gs)
            self._descend_run(nf)

        self._expand_nn_terminal()

    def _descend_propose(self, team: List[int]) -> None:
        if not team or self._node.get("type") == "TERMINAL_MERLIN":
            return
        if self._node.get("type") == "TERMINAL_PROPOSE_NN":
            self._expand_nn_terminal()
        if self._node.get("type") != "TERMINAL_PROPOSE_NN" and "propose_options" in self._node:
            bits = proposal_to_bitstring([int(x) for x in team])
            opts = self._node["propose_options"]
            child_index = opts.index(bits)
            self._node = self._node["children"][child_index]

    def _descend_vote(self, votes: Dict[int, str], n_play: int) -> None:
        if self._node.get("type") == "TERMINAL_MERLIN":
            return
        if self._node.get("type") == "TERMINAL_PROPOSE_NN":
            self._expand_nn_terminal()
        if "children" not in self._node:
            return
        idx = votes_to_bitstring(votes, n_play)
        try:
            self._node = self._node["children"][idx]
        except (IndexError, KeyError, TypeError):
            pass

    def _descend_run(self, num_fails: int) -> None:
        if self._node.get("type") == "TERMINAL_MERLIN":
            return
        if self._node.get("type") == "TERMINAL_PROPOSE_NN":
            self._expand_nn_terminal()
        if "children" not in self._node:
            return
        nf = int(max(0, min(num_fails, len(self._node["children"]) - 1)))
        try:
            self._node = self._node["children"][nf]
        except (IndexError, KeyError, TypeError):
            pass

    def _infer_num_fails(self, old_gs: Dict[str, Any], new_gs: Dict[str, Any]) -> int:
        if int(new_gs.get("mission_successes", 0)) > int(old_gs.get("mission_successes", 0)):
            return 0
        if int(new_gs.get("mission_failures", 0)) > int(old_gs.get("mission_failures", 0)):
            ma = old_gs.get("mission_actions") or new_gs.get("mission_actions") or {}
            fc = sum(1 for v in ma.values() if str(v).lower() == "fail")
            return max(1, fc) if fc else 1
        return 0

    def _expand_nn_terminal(self) -> None:
        while self._node.get("type") == "TERMINAL_PROPOSE_NN":
            exe, cwd = get_cached_deeprole_paths(self.binary)
            if not Path(exe).is_file():
                break
            snap_gs: Dict[str, Any] = {
                "mission_successes": self._node.get("succeeds", 0),
                "phase": "Discussion",
            }
            if _should_skip_deeprole(snap_gs, cwd, self.nn_folder):
                break
            nxt = dr_run_deeprole_on_node(
                self._node,
                self.iterations,
                self.wait_iterations,
                no_zero=self.no_zero,
                nn_folder=self.nn_folder,
                binary=self.binary,
            )
            if not nxt:
                break
            self._node = nxt
            self._belief = list(self._node.get("new_belief", self._belief))
        typ = str(self._node.get("type", ""))
        if typ.startswith("TERMINAL_") and typ != "TERMINAL_MERLIN":
            return

    # -- action sampling ---------------------------------------------------

    def _act_propose(self, gs: Dict[str, Any]) -> str:
        n = int(gs.get("num_players", 5))
        mi = int(gs.get("mission_index", 0))
        k = _team_size(n, mi)
        node = self._node
        if "propose_strat" in node and "propose_options" in node:
            pr = self._perspective
            opts = node["propose_options"]
            strat = node["propose_strat"][pr]
            j = _sample_index(list(strat))
            bits = int(opts[j])
            team = [i for i in range(n) if (1 << i) & bits]
            while len(team) != k:
                j = random.randrange(len(opts))
                bits = int(opts[j])
                team = [i for i in range(n) if (1 << i) & bits]
            return f"<team>{team}</team>"
        team = random.sample(range(n), k)
        team.sort()
        return f"<team>{team}</team>"

    def _act_vote(self, gs: Dict[str, Any]) -> str:
        node = self._node
        pl = self._player
        pr = self._perspective
        if "vote_strat" in node:
            row = node["vote_strat"]
            if isinstance(row, list) and pl < len(row) and row[pl] is not None:
                probs = row[pl][pr]
                up = _sample_index(list(probs)) == 1
                return "<vote>approve</vote>" if up else "<vote>reject</vote>"
        return random.choice(("<vote>approve</vote>", "<vote>reject</vote>"))

    def _act_mission(self, gs: Dict[str, Any]) -> str:
        node = self._node
        pl = self._player
        pr = self._perspective
        if "mission_strat" in node:
            ms = node.get("mission_strat")
            if ms and pl < len(ms) and ms[pl] is not None:
                probs = ms[pl][pr]
                fail = _sample_index(list(probs)) == 1
                tag = "fail" if fail else "success"
                return f"<action>{tag}</action>"
        if self._role == "merlin" or self._role == "servant":
            return "<action>success</action>"
        return random.choice(("<action>success</action>", "<action>fail</action>"))

    # -- fallbacks ---------------------------------------------------------

    def _fallback_guess_merlin(self, gs: Dict[str, Any]) -> str:
        n = int(gs.get("num_players", 5))
        guess = random.randrange(0, n)
        return f"<merlin_guess>{guess}</merlin_guess>"

    def _fallback_mechanical(self, gs: Dict[str, Any], phase: str) -> str:
        ph = phase.lower().replace("_", "-")
        n = int(gs.get("num_players", 5))
        mi = int(gs.get("mission_index", 0))
        if ph in ("team-proposal", "team proposal") and int(gs.get("leader_pid", -1)) == self._player:
            k = _team_size(n, mi)
            team = sorted(random.sample(range(n), k))
            return f"<team>{team}</team>"
        if ph in ("voting",):
            return random.choice(("<vote>approve</vote>", "<vote>reject</vote>"))
        if ph in ("mission",):
            if self._player in (gs.get("team_proposal") or []):
                if self._role == "minion":
                    return random.choice(("<action>success</action>", "<action>fail</action>"))
                return "<action>success</action>"
        return random.choice(_DISCUSSION_FALLBACKS)


__all__ = [
    "DeepRoleIntegrator",
    "ASSIGNMENT_TO_VIEWPOINT",
    "_DEEPROLE_EVIL",
    "build_hidden_state_tables",
    "get_cached_assignment_viewpoint",
    "get_cached_hidden_state_tables",
    "get_cached_deeprole_paths",
    "dr_find_deeprole_binary_and_cwd",
    "dr_run_deeprole_on_node",
    "dr_normalize_observation",
    "dr_parse_game_states",
    "dr_phase_str",
    "proposal_to_bitstring",
    "bitstring_to_proposal",
    "votes_to_bitstring",
    "get_start_node",
]
