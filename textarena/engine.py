"""
The TextArena game engine.

This module contains the single game loop shared by all environments. A game
declares its settings as `Param`s, implements a small set of hooks (`setup`,
`prompt`, `apply`, and optionally `render`, `roles`, `on_turn_limit`,
`on_invalid_limit`) and the engine owns everything else: parameter validation,
turn rotation, invalid-move handling, eliminations, turn limits, reward
bookkeeping, observation routing, and logging.
"""
import re
import copy
import json
import math
import random
import logging
import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from textarena.core import Env, ObservationType, GAME_ID

logger = logging.getLogger(__name__)


@dataclass
class Outcome:
    """Terminal result of a game: a reward per player and a reason."""
    rewards: Dict[int, float]
    reason: str


@dataclass
class Invalid:
    """Returned by `apply` when the submitted action is illegal.

    The engine handles the retry/escalation policy; `apply` must not have
    mutated the game state before returning this.
    """
    reason: str


@dataclass
class Retryable:
    """The action could not be processed because infrastructure was unavailable.

    `reason` is shown to the player. `error`, the underlying exception, is only logged and attached to the error
    raised once retries run out, because it may quote hidden information such as a game master's raw answer.
    """
    reason: str
    error: Optional[BaseException] = None


@dataclass(frozen=True)
class Param:
    """A game setting, declared as a class attribute: ``max_turns = Param(100, "Moves before a draw.", min=1)``.

    The type is that of the default unless given. `GameEnv.__init__` validates every value and sets it as an
    instance attribute; the docs generator lists the description and the accepted values in the game's README.
    `check` covers any other rule, described in words by `rule` (e.g. "a list of unique names").
    """
    default: Any
    description: str
    type: Optional[type] = None
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[Tuple[Any, ...]] = None
    optional: bool = False
    check: Optional[Callable[[Any], bool]] = None
    rule: Optional[str] = None

    @property
    def kind(self) -> type:
        return self.type or (type(self.default) if self.default is not None else object)

    def describe(self) -> str:
        """The accepted values in words, e.g. "an integer from 1 to 100"."""
        if self.rule:
            text = self.rule
        elif self.choices is not None:
            text = "one of " + ", ".join(repr(choice) for choice in self.choices)
        else:
            nouns = {bool: "True or False", int: "an integer", float: "a number", str: "a string",
                     list: "a list", tuple: "a list", dict: "a mapping"}
            text = nouns.get(self.kind, "any value")
            if self.min is not None and self.max is not None:
                text += f" from {self.min} to {self.max}"
            elif self.min is not None:
                text += f" of at least {self.min}"
            elif self.max is not None:
                text += f" of at most {self.max}"
        return text + (" or None" if self.optional or self.default is None else "")

    def validate(self, name: str, value: Any) -> Any:
        """The value to store, or ValueError if it is not accepted."""
        if value is None and (self.optional or self.default is None):
            return None
        kind = self.kind
        if kind is bool:
            ok = isinstance(value, bool)
        elif kind is int:
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif kind is float:
            try:
                ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            except OverflowError:  # integers beyond the float range
                ok = False
            value = float(value) if ok else value
        elif kind in (list, tuple):
            ok = isinstance(value, (list, tuple))
            value = kind(value) if ok else value
        elif kind is dict:
            ok = isinstance(value, dict)
            value = dict(value) if ok else value
        else:
            ok = kind is object or isinstance(value, kind)
        ok = ok and (self.min is None or value >= self.min) and (self.max is None or value <= self.max)
        ok = ok and (self.choices is None or value in self.choices)
        if ok and self.check is not None:
            try:
                ok = bool(self.check(value))
            except Exception:
                ok = False
        if not ok:
            try:
                shown = repr(value)
            except ValueError:  # e.g. integers with more digits than Python will print
                shown = "a value too large to print"
            if len(shown) > 80:
                shown = shown[:77] + "..."
            raise ValueError(f"{name} must be {self.describe()}, received {shown}")
        return value


# One entry in the event log. `to_id == -1` means visible to everyone.
Event = Tuple[int, str, ObservationType, int]


class GameState:
    """Pure data record for a running game.

    All behavior lives in `GameEnv`; this object only holds state so it can be
    snapshotted, serialized, and inspected.
    """

    def __init__(self, num_players: int, max_turns: Optional[int], error_allowance: int, seed: Optional[int] = None):
        self.num_players = num_players
        self.max_turns = max_turns
        self.error_allowance = error_allowance
        self.seed = seed
        self.actions: List[Any] = []  # every processed action, for GameEnv.record()
        self.external_answers: List[Any] = []  # answers returned by GameEnv.ask(), for replays

        self.current_player_id: int = 0
        self.turn: int = 0
        self.done: bool = False
        self.rewards: Optional[Dict[int, float]] = None
        self.game_state: Dict[str, Any] = {}
        self.role_mapping: Dict[int, str] = {}
        self.game_info: Dict[int, Dict[str, Any]] = {
            pid: {"role": f"Player {pid}", "invalid_move": False, "turn_count": 0} for pid in range(num_players)
        }
        self.eliminated: List[int] = []  # in order of elimination
        self.error_count: int = 0  # consecutive invalid moves by the current player
        self.retry_count: int = 0  # consecutive actions an external service could not process
        self.next_player_override: Optional[int] = None

        self.events: List[Event] = []
        self._cursors: Dict[int, int] = {pid: 0 for pid in range(num_players)}

    # -- observation routing ------------------------------------------------
    def add_event(self, from_id: int, message: str, observation_type: ObservationType, to_id: int = -1):
        self.events.append((from_id, message, observation_type, to_id))

    def get_current_player_observation(self) -> List[Tuple[int, str, ObservationType]]:
        pid = self.current_player_id
        start = self._cursors[pid]
        self._cursors[pid] = len(self.events)
        return [(f, m, t) for (f, m, t, to) in self.events[start:] if to == -1 or to == pid]

    @property
    def logs(self) -> List[Tuple[int, str]]:
        """Full chronological log of every event, for renderers and replays."""
        return [(f, m) for (f, m, _, _) in self.events]

    @property
    def observations(self) -> Dict[int, List[Tuple[int, str, ObservationType]]]:
        """Pending (not yet consumed) observations per player as (sender, message, type) tuples."""
        return {
            pid: [(f, m, t) for (f, m, t, to) in self.events[self._cursors[pid]:] if to == -1 or to == pid]
            for pid in range(self.num_players)
        }

    # -- helpers -------------------------------------------------------------
    def is_player_alive(self, pid: int) -> bool:
        return pid not in self.eliminated

    @property
    def alive_players(self) -> List[int]:
        return [pid for pid in range(self.num_players) if pid not in self.eliminated]

    def next_alive_player(self, after: Optional[int] = None) -> Optional[int]:
        start = self.current_player_id if after is None else after
        for offset in range(1, self.num_players + 1):
            pid = (start + offset) % self.num_players
            if pid not in self.eliminated:
                return pid
        return None

    def close(self):
        return self.rewards, self.game_info


class GameEnv(Env):
    """Base class for all game environments.

    Subclasses implement:
        setup() -> Dict[str, Any]        build and return the initial game_state (required)
        prompt(player_id) -> str         the initial prompt for a player (required)
        apply(player_id, move)           apply one action; return None to continue,
                                         Outcome to end, Invalid for a bad action, or
                                         Retryable for infrastructure failure (required)
        render(player_id) -> str|None    board string shown to the player about to act (optional)
        roles() -> Dict[int, str]        public role names, defaults to "Player {i}" (optional)
        on_turn_limit() -> Outcome       outcome when max_turns is reached; defaults to a draw (optional)
        on_invalid_limit(pid) -> Outcome|None
                                         called when a player exhausts the error allowance;
                                         the default eliminates them (see method docs) (optional)

    Settings that `ta.make` can override are declared as `Param` class attributes; `GameEnv.__init__` validates
    them. A game only defines `__init__` (calling `super().__init__(**kwargs)` first) for derived values or rules
    that involve several parameters.

    Class-level configuration:
        min_players / max_players        allowed player counts (set them in __init__ when they depend on configuration)
        default_num_players              used when reset() is called without num_players
        action_pattern                   regex; if set, the engine extracts the move
                                         (an `re.Match`) and rejects non-matching actions
        broadcast_actions                if False, raw actions are only echoed to their author
        mdp_includes_actions             if False, the -mdp observation leaves out raw player actions because the
                                         board and game messages already capture the state (most board games)
        error_allowance                  consecutive invalid moves allowed before escalation
        max_action_chars                 maximum input size accepted before parsing/logging
    """

    min_players: int = 1
    max_players: Optional[int] = None
    default_num_players: Optional[int] = None
    action_pattern: Optional[str] = None
    broadcast_actions: bool = True
    mdp_includes_actions: bool = True
    error_allowance: int = 1
    max_action_chars: int = 32_768
    max_consecutive_retries: int = 5  # Retryable results in a row before step() raises
    # Noun phrase describing a valid action, appended to format errors when action_pattern does not match,
    # e.g. "a cell number from 0 to 8, for example '4'". May be overridden per instance or as a property.
    action_format: Optional[str] = None
    snapshot_excluded_attributes: Tuple[str, ...] = ()

    max_turns: Optional[int] = None  # usually declared as a Param
    parameters: Dict[str, Param] = {}  # collected from the Param class attributes, base classes first
    state: GameState
    rng: random.Random

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.parameters = {
            name: value for klass in reversed(cls.__mro__) for name, value in vars(klass).items() if isinstance(value, Param)
        }

    def __init__(self, **kwargs):
        unknown = sorted(set(kwargs) - set(self.parameters))
        if unknown:
            raise TypeError(f"{type(self).__name__.removesuffix('Env')} has no parameter {unknown[0]!r}")
        for name, param in self.parameters.items():
            setattr(self, name, param.validate(name, kwargs.get(name, param.default)))

    # ------------------------------------------------------------------ hooks
    def setup(self) -> Dict[str, Any]:
        raise NotImplementedError

    def prompt(self, player_id: int) -> str:
        raise NotImplementedError

    def apply(self, player_id: int, move) -> Union[Outcome, Invalid, Retryable, None]:
        raise NotImplementedError

    def render(self, player_id: int) -> Optional[str]:
        return None

    def roles(self) -> Dict[int, str]:
        return {pid: f"Player {pid}" for pid in range(self.state.num_players)}

    def check_num_players(self, num_players: int) -> None:
        """Raise ValueError for player counts within min/max_players that the game still cannot use."""
        return None

    def on_start(self):
        """Called once after the initial prompts are sent, e.g. to deal private cards."""
        return None

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        """Who sees the raw action: -1 for everyone (default), a player id for
        just them, or None to suppress the echo entirely (the game can then emit
        its own sanitized description inside `apply`)."""
        return -1 if self.broadcast_actions else player_id

    def on_turn_limit(self) -> Outcome:
        return self.draw(reason="The turn limit has been reached.")

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[Outcome]:
        """Default escalation: eliminate the offender.

        If fewer than two players remain alive, the game ends (the offender
        loses; any remaining player wins). Otherwise the game continues
        without the eliminated player. A single-player game ends with 0, the
        bottom of its 0-to-1 score. Override for custom semantics.
        """
        self.eliminate(player_id)
        alive = self.state.alive_players
        if len(alive) == 0:  # single-player game
            return Outcome(rewards={player_id: 0}, reason=f"Invalid Move: {reason}")
        if len(alive) == 1:
            return self.winner(alive[0], reason=f"Player {player_id} made an invalid move. Reason: {reason}")
        self.broadcast(f"Player {player_id} was eliminated for repeated invalid moves.", ObservationType.GAME_ADMIN)
        return None

    # ------------------------------------------------------- outcome factories
    def winner(self, player_ids: Union[int, List[int]], reason: str) -> Outcome:
        if isinstance(player_ids, int):
            player_ids = [player_ids]
        rewards = {pid: (1 if pid in player_ids else -1) for pid in range(self.state.num_players)}
        return Outcome(rewards=rewards, reason=reason)

    def loser(self, player_ids: Union[int, List[int]], reason: str) -> Outcome:
        if isinstance(player_ids, int):
            player_ids = [player_ids]
        winners = [pid for pid in range(self.state.num_players) if pid not in player_ids]
        rewards = {pid: (1 if pid in winners else -1) for pid in range(self.state.num_players)}
        return Outcome(rewards=rewards, reason=reason)

    def draw(self, reason: str) -> Outcome:
        return Outcome(rewards={pid: 0 for pid in range(self.state.num_players)}, reason=reason)

    def outcome(self, rewards: Dict[int, float], reason: str) -> Outcome:
        return Outcome(rewards=rewards, reason=reason)

    def invalid(self, reason: str) -> Invalid:
        return Invalid(reason=reason)

    def retryable(self, reason: str, error: Optional[BaseException] = None) -> Retryable:
        return Retryable(reason=reason, error=error)

    # ------------------------------------------------------------ game helpers
    @property
    def game_state(self) -> Dict[str, Any]:
        return self.state.game_state

    @property
    def current_player_id(self) -> int:
        return self.state.current_player_id

    def message(self, player_id: int, message: str, observation_type: ObservationType = ObservationType.GAME_MESSAGE, from_id: int = GAME_ID):
        """Send a message visible to a single player."""
        self.state.add_event(from_id, message, observation_type, to_id=player_id)

    def broadcast(self, message: str, observation_type: ObservationType = ObservationType.GAME_MESSAGE, from_id: int = GAME_ID):
        """Send a message visible to every player."""
        self.state.add_event(from_id, message, observation_type, to_id=-1)

    def set_next_player(self, player_id: int):
        """Choose who acts next instead of the default round-robin rotation."""
        self.state.next_player_override = player_id

    def set_current_player(self, player_id: int):
        """Immediately set the acting player.

        Use this during setup or exceptional flows (such as an invalid move
        that forfeits the turn). During a normal valid action, prefer
        `set_next_player`, which applies after turn bookkeeping.
        """
        if not 0 <= player_id < self.state.num_players:
            raise ValueError(f"Unknown player id: {player_id}")
        if not self.state.is_player_alive(player_id):
            raise ValueError(f"Player {player_id} has been eliminated")
        self.state.current_player_id = player_id

    def eliminate(self, player_id: int):
        """Remove a player from the turn rotation."""
        if player_id not in self.state.eliminated:
            self.state.eliminated.append(player_id)

    def set_role(self, player_id: int, role: str):
        """Record a (possibly secret) role in game_info, e.g. for RL training."""
        self.state.game_info[player_id]["role"] = role

    def strip_role_tags(self, text: str) -> str:
        """Remove sender labels such as ``[GAME]`` or ``[Player 1]`` from player-written text.

        Use this before relaying chat so a player cannot impersonate the game or
        another player. Nested attempts like ``[GA[GAME]ME]`` are removed too.
        """
        tags = [f"[{role}]" for role in self.state.role_mapping.values() if role]
        kept: List[str] = []
        for char in text:
            kept.append(char)
            if char != "]":
                continue
            for tag in tags:
                if len(kept) >= len(tag) and "".join(kept[-len(tag):]) == tag:
                    del kept[-len(tag):]
                    break
        return "".join(kept)

    # -------------------------------------------------------------- Env API
    def reset(self, num_players: Optional[int] = None, seed: Optional[int] = None):
        if num_players is None:
            num_players = self.default_num_players
        if num_players is None and self.min_players == self.max_players:
            num_players = self.min_players
        if (
            isinstance(num_players, bool)
            or not isinstance(num_players, int)
            or num_players < self.min_players
            or (self.max_players is not None and num_players > self.max_players)
        ):
            if self.max_players is None:
                supported = f"{self.min_players} or more players"
            elif self.max_players == self.min_players:
                supported = f"exactly {self.min_players} player{'' if self.min_players == 1 else 's'}"
            else:
                supported = f"{self.min_players} to {self.max_players} players"
            game = type(self).__name__.removesuffix("Env")
            raise ValueError(f"{game} needs {supported}, received {num_players!r}.")
        self.check_num_players(num_players)
        if seed is None:
            # A concrete seed keeps every game replayable; SystemRandom leaves Python's global random state alone.
            seed = random.SystemRandom().randrange(2**63)
        self.rng = random.Random(seed)
        self.state = GameState(num_players, self.max_turns, self.error_allowance, seed=seed)
        self.state.game_state = self.setup()
        self.state.role_mapping = dict(self.roles())
        self.state.role_mapping.setdefault(GAME_ID, "GAME")
        for pid in range(num_players):
            if self.state.game_info[pid]["role"] == f"Player {pid}":
                self.set_role(pid, self.state.role_mapping.get(pid, f"Player {pid}"))
        for pid in range(num_players):
            self.message(pid, self.prompt(player_id=pid), ObservationType.PROMPT)
        self.on_start()
        self._send_render()

    def step(self, action: str) -> bool:
        """Apply the acting player's action; returns whether the game is over."""
        if self.state.done:
            return True
        pid = self.state.current_player_id
        self.state.actions.append(action)
        answers_before = len(self.state.external_answers)
        if not isinstance(action, str):
            self._handle_invalid(pid, "Actions must be strings.")
            self._send_render()
            return self.state.done
        if len(action) > self.max_action_chars:
            self._handle_invalid(
                pid,
                f"Action exceeds the maximum length of {self.max_action_chars} characters.",
            )
            self._send_render()
            return self.state.done

        # Surrounding whitespace is never meaningful, and long whitespace runs make
        # patterns like r"^\s*(...)\s*$" backtrack quadratically.
        action = action.strip()
        # Older prompts asked for moves in brackets ("[e2e4]"). One surrounding pair is dropped here so that
        # games only parse bare moves; text with inner brackets is left alone because the outer pair may not match.
        if action[:1] == "[" and action[-1:] == "]" and "[" not in action[1:-1] and "]" not in action[1:-1]:
            action = action[1:-1].strip()

        # The echo target depends on the phase before the action is applied.
        echo_target = self.action_echo_target(pid, action)
        echo_index = len(self.state.events)

        # parse and apply
        if self.action_pattern is not None:
            # action_pattern games take single-line commands, so whitespace runs carry no meaning.
            match = re.search(self.action_pattern, " ".join(action.split()), re.DOTALL)
            if match is not None:
                result = self.apply(pid, match)
            else:
                reason = "The submitted move does not follow the correct format."
                result = Invalid(f"{reason} Expected {self.action_format}." if self.action_format else reason)
        else:
            result = self.apply(pid, action)

        # The echo goes before anything apply() emitted. Rejected or unprocessed actions are
        # shown only to their author, so an invalid move is never a free-text channel to others.
        if echo_target is not None:
            if isinstance(result, (Invalid, Retryable)):
                echo_target = pid
            self.state.events.insert(
                echo_index, (pid, self.strip_role_tags(action), ObservationType.PLAYER_ACTION, echo_target)
            )

        if not isinstance(result, Retryable):
            self.state.retry_count = 0
        if isinstance(result, Invalid):
            self._handle_invalid(pid, result.reason)
        elif isinstance(result, Retryable):
            # An unprocessed action is not part of the game, so replays skip it.
            self.state.actions.pop()
            del self.state.external_answers[answers_before:]
            self.state.retry_count += 1
            cause = f" ({type(result.error).__name__}: {result.error})" if result.error is not None else ""
            logger.warning("%s could not process an action: %s%s", type(self).__name__, result.reason, cause)
            if self.state.retry_count > self.max_consecutive_retries:
                # A dead service would otherwise ask the player to retry forever.
                raise RuntimeError(
                    f"{type(self).__name__} could not process {self.state.retry_count} actions in a row "
                    f"because an external service is unavailable. Last reason: {result.reason}{cause}"
                ) from result.error
            self.message(
                pid,
                f"The action could not be processed and was not counted. Please retry. Reason: {result.reason}",
                ObservationType.GAME_ADMIN,
            )
        elif isinstance(result, Outcome):
            self._record_completed_turn(pid)
            self._finalize(result)
        else:
            self._advance_turn(pid)

        self._send_render()
        return self.state.done

    # (get_observation and close are inherited from Env)

    # ------------------------------------------------------- record / replay
    _replay_answers: Optional[List[Any]] = None  # set by replay() so that ask() reuses recorded answers

    def ask(self, service: Callable[..., Any], *args, **kwargs) -> Any:
        """Call an outside service such as an LLM judge. Replays reuse the recorded answer instead of calling it."""
        answer = self._replay_answers.pop(0) if self._replay_answers else service(*args, **kwargs)
        self.state.external_answers.append(answer)
        return answer

    def record(self) -> Dict[str, Any]:
        """Everything `replay` needs to rebuild this game: its class, parameters, player count, seed and actions.

        Parameters that cannot be stored as JSON (such as a custom jury class) are left out and take their defaults.
        """
        parameters = {}
        for name in self.parameters:
            value = getattr(self, name)
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                continue
            parameters[name] = list(value) if isinstance(value, tuple) else value
        return {
            "game": f"{type(self).__module__}:{type(self).__qualname__}",
            "env_id": getattr(self, "env_id", None),
            "parameters": parameters,
            "num_players": self.state.num_players,
            "seed": self.state.seed,
            "actions": list(self.state.actions),
            "external_answers": list(self.state.external_answers),
        }

    # ---------------------------------------------------------- snapshotting
    def snapshot(self) -> Dict[str, Any]:
        """Capture privileged full state for restore/debugging.

        Snapshots may contain hidden cards, answers, and roles. They must never
        be included in player observations.
        """
        memo: Dict[int, Any] = {}
        state = copy.deepcopy(self.state, memo)
        excluded = set(self.snapshot_excluded_attributes)
        attributes = {
            name: copy.deepcopy(value, memo)
            for name, value in self.__dict__.items()
            if name not in {"state", "rng"} and name not in excluded
        }
        return {"state": state, "rng": self.rng.getstate(), "attributes": attributes}

    def restore(self, snapshot: Dict[str, Any]):
        memo: Dict[int, Any] = {}
        state = copy.deepcopy(snapshot["state"], memo)
        preserved = {
            name: self.__dict__[name]
            for name in self.snapshot_excluded_attributes
            if name in self.__dict__
        }
        attributes = {
            name: copy.deepcopy(value, memo)
            for name, value in snapshot.get("attributes", {}).items()
        }
        self.__dict__.clear()
        self.__dict__.update(preserved)
        self.__dict__.update(attributes)
        self.state = state
        self.rng = random.Random()
        self.rng.setstate(snapshot["rng"])

    # ------------------------------------------------------------- internals
    def _handle_invalid(self, pid: int, reason: str):
        self.state.next_player_override = None
        self.state.error_count += 1
        if self.state.error_count <= self.state.error_allowance:
            self.message(
                pid,
                f"Player {pid} attempted an invalid move. Reason: {reason} "
                "Please resubmit a valid move and remember to follow the game rules to avoid penalties.",
                ObservationType.GAME_ADMIN,
            )
            return
        self.state.error_count = 0
        self.state.game_info[pid]["invalid_move"] = True
        outcome = self.on_invalid_limit(pid, reason)
        if outcome is not None:
            self._finalize(outcome)
        elif self.state.next_player_override is not None:
            self.state.current_player_id = self.state.next_player_override
            self.state.next_player_override = None
        elif not self.state.is_player_alive(pid):
            self.state.current_player_id = self.state.next_alive_player()

    def _advance_turn(self, pid: int):
        self._record_completed_turn(pid)
        if self.state.max_turns is not None and self.state.turn >= self.state.max_turns:
            self._finalize(self.on_turn_limit())
            return
        if self.state.next_player_override is not None:
            self.state.current_player_id = self.state.next_player_override
            self.state.next_player_override = None
        else:
            nxt = self.state.next_alive_player()
            if nxt is not None:
                self.state.current_player_id = nxt

    def _record_completed_turn(self, pid: int):
        self.state.error_count = 0
        self.state.game_info[pid]["turn_count"] += 1
        self.state.turn += 1

    def _finalize(self, outcome: Outcome):
        self.state.rewards = outcome.rewards
        for pid in range(self.state.num_players):
            self.state.game_info[pid]["reason"] = outcome.reason
        self.broadcast(outcome.reason, ObservationType.GAME_ADMIN)
        self.state.done = True

    def _send_render(self):
        board = self.render(player_id=self.state.current_player_id)
        if board is not None:
            self.message(self.state.current_player_id, board, ObservationType.GAME_BOARD)


def replay(record: Dict[str, Any], steps: Optional[int] = None, game: Optional[type] = None) -> GameEnv:
    """Rebuild a game from `GameEnv.record()` and apply its first `steps` actions (all by default).

    Records name the game's class, so only TextArena's own games are imported from them; pass `game` to replay a
    game defined elsewhere. Returns the unwrapped game; its event log (`env.state.events`) holds everything every
    player saw.
    """
    if game is None:
        module_name, _, class_name = record["game"].partition(":")
        if not module_name.startswith("textarena.envs."):
            raise ValueError(f"Records only name TextArena games; pass game= to replay {record['game']!r}.")
        game = getattr(importlib.import_module(module_name), class_name)
    if not (isinstance(game, type) and issubclass(game, GameEnv)):
        raise ValueError(f"{game!r} is not a TextArena game.")
    env = game(**record["parameters"])
    env._replay_answers = list(record.get("external_answers", []))
    env.reset(num_players=record["num_players"], seed=record["seed"])
    for action in record["actions"][:steps]:
        env.step(action)
    return env
