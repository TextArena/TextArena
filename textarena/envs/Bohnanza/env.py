"""Bohnanza, the bean trading card game by Uwe Rosenberg (base game, 3-5 players)."""
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Bohnanza.renderer import format_beans, format_field, harvest_coins, ordinal, render_board

# The base game deck: 104 cards of 8 bean types. `payouts` is the beanometer: coins -> beans needed.
BEAN_TYPES: Dict[str, Dict[str, Any]] = {
    "Blue":      {"count": 20, "payouts": {1: 4, 2: 6, 3: 8, 4: 10}},
    "Chili":     {"count": 18, "payouts": {1: 3, 2: 6, 3: 8, 4: 9}},
    "Stink":     {"count": 16, "payouts": {1: 3, 2: 5, 3: 7, 4: 8}},
    "Green":     {"count": 14, "payouts": {1: 3, 2: 5, 3: 6, 4: 7}},
    "Soy":       {"count": 12, "payouts": {1: 2, 2: 4, 3: 6, 4: 7}},
    "BlackEyed": {"count": 10, "payouts": {1: 2, 2: 4, 3: 5, 4: 6}},
    "Red":       {"count": 8,  "payouts": {1: 2, 2: 3, 3: 4, 4: 5}},
    "Garden":    {"count": 6,  "payouts": {2: 2, 3: 3}},
}
DECK_SIZE = sum(config["count"] for config in BEAN_TYPES.values())

_BEAN_ALIASES = {bean.lower(): bean for bean in BEAN_TYPES}
_BEAN_ALIASES.update({"chilli": "Chili", "soya": "Soy", "blackeye": "BlackEyed"})
_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

# Exactly one bare command per action, matched against the whole whitespace-normalized action.
_SEP = r"(?:\s*:\s*|\s+)"
_NUM = r"\d{1,9}"
_COMMAND_PATTERNS = [
    ("plant", re.compile(rf"plant{_SEP}(?:in(?:to)?\s+)?(?:field\s*)?#?(?P<field>{_NUM})", re.I)),
    ("plant", re.compile(rf"plant{_SEP}(?P<bean>[a-z][a-z' \-]*?)\s+(?:in(?:to)?\s+)?(?:field\s*)?#?(?P<field>{_NUM})", re.I)),
    ("harvest", re.compile(rf"harvest{_SEP}(?:field\s*)?#?(?P<field>{_NUM})", re.I)),
    ("pass", re.compile(r"pass", re.I)),
    ("end_trading", re.compile(r"end(?:\s*trad(?:e|ing))?", re.I)),
    ("accept", re.compile(rf"accept{_SEP}(?:trade\s*)?#?(?P<trade_id>{_NUM})", re.I)),
    ("cancel", re.compile(rf"(?:cancel|withdraw){_SEP}(?:trade\s*)?#?(?P<trade_id>{_NUM})", re.I)),
    ("trade", re.compile(rf"(?:trade|offer){_SEP}(?P<offer>.+?)\s+for\s+(?P<want>.+?)(?:\s+(?:with|to)\s+(?:player\s*)?#?(?P<target>{_NUM}))?", re.I)),
    ("draw", re.compile(r"draw(?:\s+\d{1,9})?(?:\s+cards?)?", re.I)),
]
_COMMAND_PREFIX = re.compile(r"(?:plant|harvest|trade|offer|accept|cancel|withdraw|pass|draw)\b|end\s*trad", re.I)
_NOTHING = re.compile(r"nothing|none|no beans?", re.I)
_BEAN_LIST_SPLIT = re.compile(r"\s*(?:,|\+|&|\band\b)\s*", re.I)
_BEAN_AMOUNT = re.compile(rf"(?:({_NUM}|a|an|one|two|three|four|five)\s*x?\s+)?(.+)", re.I)


def normalize_command(action: str) -> str:
    text = " ".join(action.split()).strip("`'\" ")
    return text.rstrip(".!").strip()


def parse_command(action: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Parse one bare command into (name, arguments), or None if the action is not a command."""
    text = normalize_command(action)
    for name, pattern in _COMMAND_PATTERNS:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        groups = match.groupdict()
        if name == "plant":
            return name, {"bean": groups.get("bean"), "field": int(groups["field"])}
        if name == "harvest":
            return name, {"field": int(groups["field"])}
        if name in ("accept", "cancel"):
            return name, {"trade_id": int(groups["trade_id"])}
        if name == "trade":
            target = groups["target"]
            return name, {"offer": groups["offer"], "want": groups["want"], "target": None if target is None else int(target)}
        return name, {}
    return None


def canonical_bean(name: str) -> Optional[str]:
    """Map 'blue', 'Blue beans', 'black-eyed', 'Chilis', ... to the canonical bean name."""
    key = re.sub(r"[\s\-_']", "", name.lower())
    for suffix in ("beans", "bean"):
        if key.endswith(suffix) and len(key) > len(suffix):
            key = key[: -len(suffix)]
            break
    if key in _BEAN_ALIASES:
        return _BEAN_ALIASES[key]
    if key.endswith("s") and key[:-1] in _BEAN_ALIASES:
        return _BEAN_ALIASES[key[:-1]]
    return None


def parse_bean_list(text: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """Parse '2 Blue, 1 Red', 'Blue and Soy' or 'nothing' into a list of beans; returns (beans, error)."""
    text = text.strip()
    if _NOTHING.fullmatch(text):
        return [], None
    parts = _BEAN_LIST_SPLIT.split(text)
    if any(not part for part in parts):
        return None, f"could not read the beans in '{text}' (write e.g. '2 Blue, 1 Red' or 'nothing')"
    beans: List[str] = []
    for part in parts:
        amount, name = _BEAN_AMOUNT.fullmatch(part).groups()
        count = 1 if amount is None else int(amount) if amount.isdigit() else _NUMBER_WORDS[amount.lower()]
        bean = canonical_bean(name)
        if bean is None:
            return None, f"unknown bean '{name}' (the bean types are {', '.join(BEAN_TYPES)})"
        if count < 1:
            return None, "every bean count must be at least 1"
        if count > BEAN_TYPES[bean]["count"]:
            return None, f"there are only {BEAN_TYPES[bean]['count']} {bean} beans in the game"
        beans.extend([bean] * count)
    for bean, count in Counter(beans).items():
        if count > BEAN_TYPES[bean]["count"]:
            return None, f"there are only {BEAN_TYPES[bean]['count']} {bean} beans in the game"
    return beans, None


def _check_int(name: str, value: Any, minimum: int, optional: bool = False):
    if value is None and optional:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}{' or None' if optional else ''}, received {value!r}")


def _join_players(player_ids: List[int]) -> str:
    names = [str(pid) for pid in player_ids]
    if len(names) == 1:
        return f"Player {names[0]}"
    return f"Players {', '.join(names[:-1])} and {names[-1]}"


class BohnanzaEnv(ta.GameEnv):
    """Bohnanza base game for 3-5 players.

    Each turn has four phases: (1) the active player plants the first one or
    two cards of their hand, (2) turns over two cards and trades with the
    other players, (3) everyone plants the beans they received (the active
    player also plants the turned-over cards they kept), and (4) the active
    player draws three cards. The game ends when the draw pile runs out for
    the `deck_cycles`-th time; the player with the most coins wins.
    """

    min_players = 3
    max_players = 5
    broadcast_actions = False  # raw actions are echoed only to their author; the game re-emits descriptions and table talk

    BEAN_TYPES = BEAN_TYPES
    HAND_SIZE = 5
    TURNED_OVER_CARDS = 2
    CARDS_DRAWN = 3
    MAX_PLANTS_FROM_HAND = 2

    def __init__(self, max_turns: Optional[int] = 3000, error_allowance: int = 3, deck_cycles: int = 3, max_trade_rounds: Optional[int] = None):
        """
        Args:
            max_turns: Step budget. When it is used up, all fields are harvested and the game is scored.
            error_allowance: Consecutive invalid moves allowed before the offender forfeits the game.
            deck_cycles: The game ends when the draw pile runs out for this many times (3 in the official rules).
            max_trade_rounds: If set, trading ends automatically once the floor has gone around the table this many times.
        """
        _check_int("max_turns", max_turns, minimum=1, optional=True)
        _check_int("error_allowance", error_allowance, minimum=0)
        _check_int("deck_cycles", deck_cycles, minimum=1)
        _check_int("max_trade_rounds", max_trade_rounds, minimum=1, optional=True)
        self.max_turns = max_turns
        self.error_allowance = error_allowance
        self.deck_cycles = deck_cycles
        self.max_trade_rounds = max_trade_rounds

    # ------------------------------------------------------------------ hooks
    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        deck = [bean for bean, config in BEAN_TYPES.items() for _ in range(config["count"])]
        self.rng.shuffle(deck)
        num_fields = 3 if num_players == 3 else 2
        players = {}
        for pid in range(num_players):
            hand = [deck.pop() for _ in range(self.HAND_SIZE)]  # hand[0] is the front card
            players[pid] = {"hand": hand, "fields": [None] * num_fields, "coins": 0}
        return {
            "deck": deck,  # the top of the draw pile is the end of the list
            "discard_pile": [],
            "deck_cycles_completed": 0,  # how often the draw pile has run out
            "game_ending": False,  # the draw pile ran out for the last time; the current turn finishes phases 2-3 at most
            "turn_number": 0,
            "active_player": 0,
            "current_phase": "plant",
            "planted_from_hand": 0,
            "face_up_cards": [],
            "active_trades": {},
            "trade_counter": 0,
            "trade_round": 0,
            "mandatory_plants": {pid: [] for pid in range(num_players)},  # beans set aside for phase 3
            "players": players,
        }

    def on_start(self):
        self.set_current_player(self._start_turn(0))

    def prompt(self, player_id: int) -> str:
        num_fields = len(self.game_state["players"][player_id]["fields"])
        beanometers = "\n".join(
            f"  {bean:<9} ({config['count']:>2} cards): "
            + ", ".join(f"{needed} beans = {coins} coin{'s' if coins != 1 else ''}" for coins, needed in sorted(config["payouts"].items()))
            for bean, config in BEAN_TYPES.items()
        )
        return f"""You are Player {player_id} in a {self.state.num_players}-player game of Bohnanza, the bean trading card game.

GOAL
Finish with the most coins. You earn coins by harvesting your bean fields: the more beans of one kind a field holds, the more coins it is worth.

YOUR CARDS
- You have {num_fields} bean fields. A field holds any number of beans, but only one kind of bean at a time.
- Your hand is private and you may NEVER rearrange it: you always plant from the front of your hand, and new cards go to the back.

A TURN (Player 0 starts, then Player 1, Player 2, ... in seat order)
1. Plant: the active player must plant the first card of their hand and may then plant the next one (at most two). Skipped if their hand is empty.
2. Turn over and trade: the top two cards of the draw pile are turned face up. They belong to the active player, who may keep or trade them. Only the active player trades, with any of the other players, using hand cards from any position (the active player may also use the face-up cards). Any number of beans may be traded for any number, or given as a gift. Beans received in a trade are set aside (they cannot be traded again) and must be planted in phase 3. The floor passes around the table, starting with the active player, until the active player ends trading.
3. Plant: everyone plants the beans they received, and the active player also plants the face-up cards they kept, in any order (active player first, then clockwise).
4. Draw: the active player automatically draws three cards to the back of their hand, and the next player's turn begins.

HARVESTING
- Whenever it is your move you may harvest one of your fields (always the whole field). If a bean you must plant fits no field, harvest one first.
- Bean protection rule: you may not harvest a field holding a single bean while another of your fields holds two or more beans.
- As many of the harvested cards as you earn coins become coins (they leave the game); the rest go to the discard pile.

BEANOMETERS
{beanometers}

GAME END
When the draw pile runs out, the discard pile is shuffled into a new draw pile. The game ends when the draw pile runs out for the {ordinal(self.deck_cycles)} time; if that happens while cards are being turned over, the turn still finishes phases 2 and 3. Then all fields are harvested; cards in hand are worth nothing. The most coins wins; a tie goes to the tied player sitting furthest clockwise from Player 0 (the highest player number).

ACTIONS (submit exactly one bare action, e.g. plant 1)
- plant <field>             Phase 1: plant the first card of your hand, e.g. plant 1
- plant <bean> <field>      Phase 3: plant one of your set-aside beans, e.g. plant Blue 2 (plant 2 also works if they are all the same kind)
- harvest <field>           Harvest one of your fields, e.g. harvest 2 (this does not use up your move)
- pass                      Phase 1: stop after planting one card. Trading: give the floor to the next player.
- trade <offer> for <want>  Trading: propose a trade, e.g. trade 2 Chili for 1 Blue, trade Soy for nothing (a gift), trade nothing for Red (ask for a gift). The active player's offers are open to everyone unless addressed with "with Player N" (e.g. trade Soy for Red with Player 2); everyone else's offers go to the active player.
- accept <id>               Trading: accept a trade offered to you, e.g. accept 3
- cancel <id>               Trading: withdraw one of your own open offers, e.g. cancel 3
- end trading               Trading, active player only: stop trading and go on to phase 3
During trading, any other text is said aloud to the whole table."""

    def render(self, player_id: int) -> str:
        board = render_board(self.game_state, player_id, BEAN_TYPES, self.deck_cycles)
        return f"{board}\n{self._options_text(player_id)}"

    def get_board_str(self) -> str:
        return render_board(self.game_state, self.state.current_player_id, BEAN_TYPES, self.deck_cycles)

    def on_turn_limit(self) -> ta.Outcome:
        return self._final_outcome(f"The turn limit of {self.state.max_turns} steps was reached, so the game is scored now.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        self.game_state["current_phase"] = "game_over"
        rewards = {pid: (-1 if pid == player_id else 0) for pid in range(self.state.num_players)}
        return self.outcome(rewards, reason=f"Player {player_id} made too many invalid moves and forfeits the game. Last error: {reason}")

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        command = parse_command(action)
        if command is None:
            result = self._free_text(player_id, action)
        else:
            name, arguments = command
            result = getattr(self, f"_cmd_{name}")(player_id, **arguments)
        if isinstance(result, (ta.Invalid, ta.Outcome)):
            return result
        self.set_next_player(result)
        return None

    # --------------------------------------------------------------- commands
    # Each handler validates completely before mutating anything and returns an
    # Invalid, a terminal Outcome, or the id of the player who moves next.
    def _cmd_plant(self, player_id: int, bean: Optional[str], field: int) -> Union[ta.Invalid, ta.Outcome, int]:
        phase = self.game_state["current_phase"]
        if phase == "plant":
            return self._plant_from_hand(player_id, bean, field)
        if phase == "plant_mandatory":
            return self._plant_set_aside(player_id, bean, field)
        return self.invalid("You cannot plant during trading: beans received in trades are set aside and planted in phase 3, after the active player ends trading.")

    def _cmd_harvest(self, player_id: int, field: int) -> Union[ta.Invalid, int]:
        player = self.game_state["players"][player_id]
        error = self._harvest_error(player, field)
        if error:
            return self.invalid(error)
        bean, count, coins = self._harvest(player_id, field - 1)
        self.broadcast(
            f"Player {player_id} harvested field {field} ({bean} x{count}) for {coins} coin{'s' if coins != 1 else ''}; "
            f"{count - coins} card{'s' if count - coins != 1 else ''} went to the discard pile. "
            f"Player {player_id} now has {player['coins']} coins.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        return player_id  # harvesting does not use up the move

    def _cmd_pass(self, player_id: int) -> Union[ta.Invalid, ta.Outcome, int]:
        gs = self.game_state
        phase = gs["current_phase"]
        if phase == "plant":
            hand = gs["players"][player_id]["hand"]
            if gs["planted_from_hand"] == 0 and hand:
                return self.invalid(f"You must plant the first card of your hand ({hand[0]}) before you can pass: use plant <field>.")
            self.broadcast(f"Player {player_id} stops planting.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return self._begin_trading()
        if phase == "draw_trade":
            self.broadcast(f"Player {player_id} passes.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return self._pass_floor(player_id)
        return self.invalid(f"You cannot pass: first plant your set-aside beans ({format_beans(gs['mandatory_plants'][player_id])}) with plant <bean> <field>.")

    def _cmd_end_trading(self, player_id: int) -> Union[ta.Invalid, ta.Outcome, int]:
        gs = self.game_state
        if gs["current_phase"] != "draw_trade":
            return self.invalid(f"There is no trading going on right now. {self._phase_hint(player_id)}")
        if player_id != gs["active_player"]:
            return self.invalid(f"Only the active player (Player {gs['active_player']}) can end trading. Use pass to give the floor to the next player.")
        self.broadcast(f"Player {player_id} ends trading.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return self._end_trading()

    def _cmd_trade(self, player_id: int, offer: str, want: str, target: Optional[int]) -> Union[ta.Invalid, ta.Outcome, int]:
        gs = self.game_state
        if gs["current_phase"] != "draw_trade":
            return self.invalid(f"Trades can only be proposed during the trading phase (phase 2). {self._phase_hint(player_id)}")
        offer_beans, error = parse_bean_list(offer)
        if error:
            return self.invalid(f"Invalid offer: {error}.")
        want_beans, error = parse_bean_list(want)
        if error:
            return self.invalid(f"Invalid request: {error}.")
        if not offer_beans and not want_beans:
            return self.invalid("A trade cannot be nothing for nothing.")
        active, num_players = gs["active_player"], self.state.num_players
        if player_id == active:
            if target is not None and (target == player_id or not 0 <= target < num_players):
                return self.invalid(f"Offers can be addressed to one of the other players (Player 0 to Player {num_players - 1}), not to yourself.")
        else:
            if target is not None and target != active:
                return self.invalid(f"Only the active player trades: your offers always go to Player {active}.")
            target = active
        missing = self._missing_beans(player_id, offer_beans)
        if missing:
            where = "your hand and the face-up cards" if player_id == active else "your hand"
            return self.invalid(f"You cannot offer {format_beans(offer_beans)}: you are missing {format_beans(missing)} (you can only trade from {where}).")
        gs["trade_counter"] += 1
        trade_id = gs["trade_counter"]
        gs["active_trades"][trade_id] = {"proposer": player_id, "target": target, "offer": offer_beans, "want": want_beans, "status": "pending"}
        audience = "anyone" if target is None else f"Player {target}"
        acceptors = "Any other player" if target is None else f"Player {target}"
        self.broadcast(
            f"Trade #{trade_id}: Player {player_id} offers {format_beans(offer_beans)} for {format_beans(want_beans)} to {audience}. "
            f"{acceptors} can accept with: accept {trade_id}",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        return self._pass_floor(player_id)

    def _cmd_accept(self, player_id: int, trade_id: int) -> Union[ta.Invalid, ta.Outcome, int]:
        gs = self.game_state
        if gs["current_phase"] != "draw_trade":
            return self.invalid(f"Trades can only be accepted during the trading phase (phase 2). {self._phase_hint(player_id)}")
        trade = gs["active_trades"].get(trade_id)
        if trade is None or trade["status"] != "pending":
            return self.invalid(f"There is no open trade offer #{trade_id}.")
        if trade["proposer"] == player_id:
            return self.invalid("You cannot accept your own offer.")
        if trade["target"] is not None and trade["target"] != player_id:
            return self.invalid(f"Trade #{trade_id} is addressed to Player {trade['target']}, not to you.")
        if self._missing_beans(trade["proposer"], trade["offer"]):
            trade["status"] = "withdrawn"
            self.broadcast(f"Trade #{trade_id} is no longer possible and was withdrawn.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return player_id
        missing = self._missing_beans(player_id, trade["want"])
        if missing:
            return self.invalid(f"You cannot accept trade #{trade_id}: it asks for {format_beans(trade['want'])} and you are missing {format_beans(missing)}.")
        self._execute_trade(trade, acceptor=player_id)
        self.broadcast(
            f"Player {player_id} accepted trade #{trade_id}: Player {trade['proposer']} gave {format_beans(trade['offer'])} "
            f"and received {format_beans(trade['want'])}. Traded beans are set aside and must be planted in phase 3.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        self._withdraw_impossible_trades()
        return self._pass_floor(player_id)

    def _cmd_cancel(self, player_id: int, trade_id: int) -> Union[ta.Invalid, int]:
        gs = self.game_state
        if gs["current_phase"] != "draw_trade":
            return self.invalid(f"There are no trade offers outside the trading phase. {self._phase_hint(player_id)}")
        trade = gs["active_trades"].get(trade_id)
        if trade is None or trade["status"] != "pending":
            return self.invalid(f"There is no open trade offer #{trade_id}.")
        if trade["proposer"] != player_id:
            return self.invalid("You can only withdraw your own offers.")
        trade["status"] = "withdrawn"
        self.broadcast(f"Player {player_id} withdrew trade #{trade_id}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return player_id  # withdrawing does not use up the move

    def _cmd_draw(self, player_id: int) -> ta.Invalid:
        return self.invalid(f"There is no draw action: the active player draws three cards automatically at the end of their turn. {self._phase_hint(player_id)}")

    def _free_text(self, player_id: int, action: str) -> Union[ta.Invalid, ta.Outcome, int]:
        text = self.strip_role_tags(action).strip()
        if not text:
            return self.invalid(f"Empty action. {self._phase_hint(player_id)}")
        if self.game_state["current_phase"] != "draw_trade":
            return self.invalid(f"Unrecognized action. {self._phase_hint(player_id)}")
        if _COMMAND_PREFIX.match(normalize_command(text)):
            return self.invalid(f"Malformed command. {self._phase_hint(player_id)} Table talk must not start with a command word.")
        for pid in range(self.state.num_players):
            if pid != player_id:
                self.message(pid, text, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        return self._pass_floor(player_id)

    # ------------------------------------------------------------- planting
    def _plant_from_hand(self, player_id: int, bean: Optional[str], field: int) -> Union[ta.Invalid, ta.Outcome, int]:
        gs = self.game_state
        player = gs["players"][player_id]
        hand = player["hand"]
        if not hand:
            return self.invalid("You have no cards in hand to plant; use pass.")
        front = hand[0]
        if bean is not None:
            named = canonical_bean(bean)
            if named is None:
                return self.invalid(f"Unknown bean '{bean}'. The bean types are {', '.join(BEAN_TYPES)}.")
            if named != front:
                return self.invalid(f"The first card of your hand is {front}, not {named}. You can only plant from the front of your hand: plant <field>.")
        error = self._field_error(player, field, front)
        if error:
            return self.invalid(error)
        self._put_in_field(player, field, front)
        hand.pop(0)
        gs["planted_from_hand"] += 1
        which = "first" if gs["planted_from_hand"] == 1 else "second"
        self.broadcast(
            f"Player {player_id} planted the {which} card of their hand, {front}, in field {field} (now {format_field(player['fields'][field - 1])}).",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        if gs["planted_from_hand"] >= self.MAX_PLANTS_FROM_HAND or not hand:
            return self._begin_trading()
        return player_id

    def _plant_set_aside(self, player_id: int, bean: Optional[str], field: int) -> Union[ta.Invalid, ta.Outcome, int]:
        player = self.game_state["players"][player_id]
        pending = self.game_state["mandatory_plants"][player_id]
        if not pending:
            return self.invalid("You have no set-aside beans to plant.")
        if bean is None:
            kinds = list(dict.fromkeys(pending))
            if len(kinds) > 1:
                return self.invalid(f"You have different beans to plant ({format_beans(pending)}); name the one you want, e.g. plant {kinds[0]} {field}.")
            chosen = kinds[0]
        else:
            chosen = canonical_bean(bean)
            if chosen is None:
                return self.invalid(f"Unknown bean '{bean}'. The bean types are {', '.join(BEAN_TYPES)}.")
            if chosen not in pending:
                return self.invalid(f"You have no {chosen} to plant. Your set-aside beans: {format_beans(pending)}.")
        error = self._field_error(player, field, chosen)
        if error:
            return self.invalid(error)
        self._put_in_field(player, field, chosen)
        pending.remove(chosen)
        self.broadcast(
            f"Player {player_id} planted {chosen} in field {field} (now {format_field(player['fields'][field - 1])}).",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        if pending:
            return player_id
        return self._next_planter()

    def _field_error(self, player: Dict[str, Any], field: int, bean: str) -> Optional[str]:
        fields = player["fields"]
        if not 1 <= field <= len(fields):
            return f"There is no field {field}; your fields are numbered 1 to {len(fields)}."
        current = fields[field - 1]
        if current is not None and current[0] != bean:
            return f"Field {field} holds {format_field(current)}, so {bean} cannot be planted there. {bean} fits {self._fit_text(player, bean)}."
        return None

    @staticmethod
    def _put_in_field(player: Dict[str, Any], field: int, bean: str):
        current = player["fields"][field - 1]
        player["fields"][field - 1] = (bean, 1 if current is None else current[1] + 1)

    @staticmethod
    def _fit_text(player: Dict[str, Any], bean: str) -> str:
        fits = [f"field {number} ({format_field(field)})" for number, field in enumerate(player["fields"], start=1) if field is None or field[0] == bean]
        return " or ".join(fits) if fits else "no field: harvest a field first"

    # ------------------------------------------------------------- harvesting
    @staticmethod
    def _harvest_error(player: Dict[str, Any], field: int) -> Optional[str]:
        fields = player["fields"]
        if not 1 <= field <= len(fields):
            return f"There is no field {field}; your fields are numbered 1 to {len(fields)}."
        current = fields[field - 1]
        if current is None:
            return f"Field {field} is empty."
        if current[1] == 1 and any(other is not None and other[1] > 1 for other in fields):
            return f"Bean protection rule: field {field} holds a single bean, and you cannot harvest it while another of your fields holds more than one bean."
        return None

    def _harvest(self, player_id: int, index: int) -> Tuple[str, int, int]:
        """Harvest a whole field: coin cards leave the game, the remaining cards are discarded."""
        player = self.game_state["players"][player_id]
        bean, count = player["fields"][index]
        coins = self._calculate_harvest_coins(bean, count)
        player["fields"][index] = None
        player["coins"] += coins
        self.game_state["discard_pile"].extend([bean] * (count - coins))
        return bean, count, coins

    @staticmethod
    def _calculate_harvest_coins(bean: str, count: int) -> int:
        return harvest_coins(BEAN_TYPES[bean]["payouts"], count)

    # ---------------------------------------------------------------- trading
    def _tradeable_cards(self, player_id: int) -> List[str]:
        gs = self.game_state
        cards = list(gs["players"][player_id]["hand"])
        if gs["current_phase"] == "draw_trade" and player_id == gs["active_player"]:
            cards += gs["face_up_cards"]
        return cards

    def _missing_beans(self, player_id: int, beans: List[str]) -> List[str]:
        available = Counter(self._tradeable_cards(player_id))
        missing: List[str] = []
        for bean, needed in Counter(beans).items():
            missing += [bean] * max(0, needed - available[bean])
        return missing

    def _take_beans(self, player_id: int, beans: List[str]):
        """Remove traded beans: the active player gives face-up cards before hand cards; hand cards go front-most first."""
        gs = self.game_state
        hand, face_up = gs["players"][player_id]["hand"], gs["face_up_cards"]
        from_face_up = player_id == gs["active_player"]
        for bean in beans:
            if from_face_up and bean in face_up:
                face_up.remove(bean)
            else:
                hand.remove(bean)

    def _execute_trade(self, trade: Dict[str, Any], acceptor: int):
        gs = self.game_state
        proposer = trade["proposer"]
        self._take_beans(proposer, trade["offer"])
        self._take_beans(acceptor, trade["want"])
        gs["mandatory_plants"][acceptor].extend(trade["offer"])
        gs["mandatory_plants"][proposer].extend(trade["want"])
        trade["status"] = "accepted"
        trade["accepted_by"] = acceptor

    def _withdraw_impossible_trades(self):
        for trade_id, trade in self.game_state["active_trades"].items():
            if trade["status"] == "pending" and self._missing_beans(trade["proposer"], trade["offer"]):
                trade["status"] = "withdrawn"
                self.broadcast(f"Trade #{trade_id} is no longer possible and was withdrawn.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _pass_floor(self, player_id: int) -> Union[ta.Outcome, int]:
        gs = self.game_state
        next_pid = (player_id + 1) % self.state.num_players
        if next_pid == gs["active_player"]:
            gs["trade_round"] += 1
            if self.max_trade_rounds is not None and gs["trade_round"] > self.max_trade_rounds:
                rounds = self.max_trade_rounds
                self.broadcast(f"Trading ends automatically after {rounds} round{'s' if rounds != 1 else ''} around the table.", ta.ObservationType.GAME_MESSAGE)
                return self._end_trading()
        return next_pid

    # ------------------------------------------------------------ turn flow
    def _seat_order(self, start: int) -> List[int]:
        return [(start + offset) % self.state.num_players for offset in range(self.state.num_players)]

    def _start_turn(self, player_id: int) -> int:
        gs = self.game_state
        gs["turn_number"] += 1
        gs["active_player"] = player_id
        gs["current_phase"] = "plant"
        gs["planted_from_hand"] = 0
        if not gs["players"][player_id]["hand"]:
            self.broadcast(f"Turn {gs['turn_number']}: Player {player_id} is the active player but has no cards in hand, so phase 1 is skipped.", ta.ObservationType.GAME_MESSAGE)
            return self._begin_trading()
        self.broadcast(
            f"Turn {gs['turn_number']}: Player {player_id} is the active player. Phase 1: Player {player_id} must plant the first card of their hand and may plant the next one as well.",
            ta.ObservationType.GAME_MESSAGE,
        )
        return player_id

    def _begin_trading(self) -> int:
        gs = self.game_state
        active = gs["active_player"]
        gs["current_phase"] = "draw_trade"
        gs["active_trades"] = {}
        gs["trade_round"] = 1
        gs["face_up_cards"] = self._draw_cards(self.TURNED_OVER_CARDS)
        shown = ", ".join(gs["face_up_cards"]) if gs["face_up_cards"] else "no cards because the draw pile is empty"
        self.broadcast(
            f"Phase 2: Player {active} turns over {shown}. The face-up cards belong to Player {active}. "
            f"Trading is open: only trades with Player {active} are allowed, the floor passes around the table starting with Player {active}, "
            f"and Player {active} ends trading with: end trading",
            ta.ObservationType.GAME_MESSAGE,
        )
        return active

    def _end_trading(self) -> Union[ta.Outcome, int]:
        gs = self.game_state
        active = gs["active_player"]
        gs["mandatory_plants"][active].extend(gs["face_up_cards"])
        gs["face_up_cards"] = []
        gs["active_trades"] = {}
        gs["current_phase"] = "plant_mandatory"
        waiting = [(pid, gs["mandatory_plants"][pid]) for pid in self._seat_order(active) if gs["mandatory_plants"][pid]]
        if waiting:
            self.broadcast(
                "Phase 3: set-aside beans must now be planted (active player first, then clockwise): "
                + "; ".join(f"Player {pid}: {format_beans(beans)}" for pid, beans in waiting) + ".",
                ta.ObservationType.GAME_MESSAGE,
            )
        else:
            self.broadcast("Phase 3: nobody has beans to plant.", ta.ObservationType.GAME_MESSAGE)
        return self._next_planter()

    def _next_planter(self) -> Union[ta.Outcome, int]:
        gs = self.game_state
        for pid in self._seat_order(gs["active_player"]):
            if gs["mandatory_plants"][pid]:
                return pid
        return self._finish_turn()

    def _finish_turn(self) -> Union[ta.Outcome, int]:
        gs = self.game_state
        active = gs["active_player"]
        if gs["game_ending"]:
            return self._final_outcome("The draw pile has run out for the last time.")
        gs["current_phase"] = "draw"
        drawn = self._draw_cards(self.CARDS_DRAWN)
        gs["players"][active]["hand"].extend(drawn)
        self.broadcast(f"Phase 4: Player {active} draws {len(drawn)} card{'s' if len(drawn) != 1 else ''} and ends their turn.", ta.ObservationType.GAME_MESSAGE)
        if drawn:
            self.message(active, f"You drew {', '.join(drawn)}; they were added to the back of your hand.", ta.ObservationType.GAME_MESSAGE)
        if gs["game_ending"]:
            return self._final_outcome("The draw pile has run out for the last time.")
        return self._start_turn((active + 1) % self.state.num_players)

    # ------------------------------------------------------------ draw pile
    def _draw_cards(self, count: int) -> List[str]:
        gs = self.game_state
        drawn: List[str] = []
        for _ in range(count):
            card = self._draw_card()
            if card is None:
                break
            drawn.append(card)
            if gs["game_ending"] or not gs["deck"]:  # at most one run-out per batch of draws
                break
        return drawn

    def _draw_card(self) -> Optional[str]:
        gs = self.game_state
        if gs["game_ending"]:
            return None
        if not gs["deck"]:
            # Only reachable if the discard pile was empty when the draw pile last ran out.
            if not gs["discard_pile"]:
                self._deck_ran_out()
                return None
            self._reshuffle_deck()
        card = gs["deck"].pop()
        if not gs["deck"]:
            self._deck_ran_out()
        return card

    def _deck_ran_out(self):
        gs = self.game_state
        gs["deck_cycles_completed"] += 1
        completed = gs["deck_cycles_completed"]
        if completed >= self.deck_cycles:
            gs["game_ending"] = True
            if gs["current_phase"] == "draw_trade":
                ending = f"Player {gs['active_player']} finishes trading and planting this turn, then the game ends."
            else:
                ending = "The game ends now."
            self.broadcast(f"The draw pile has run out for the {ordinal(completed)} time. {ending}", ta.ObservationType.GAME_MESSAGE)
            return
        self.broadcast(f"The draw pile has run out ({completed} of {self.deck_cycles}).", ta.ObservationType.GAME_MESSAGE)
        self._reshuffle_deck()

    def _reshuffle_deck(self):
        gs = self.game_state
        gs["deck"], gs["discard_pile"] = gs["discard_pile"], []
        self.rng.shuffle(gs["deck"])
        if gs["deck"]:
            self.broadcast(f"The discard pile was shuffled into a new draw pile of {len(gs['deck'])} cards.", ta.ObservationType.GAME_MESSAGE)
        else:
            self.broadcast("The discard pile is empty, so there is no new draw pile yet.", ta.ObservationType.GAME_MESSAGE)

    # ------------------------------------------------------------- game end
    def _final_outcome(self, prefix: str) -> ta.Outcome:
        gs = self.game_state
        gs["current_phase"] = "game_over"
        num_players = self.state.num_players
        summaries = []
        for pid in range(num_players):
            harvested = []
            for index, field in enumerate(gs["players"][pid]["fields"]):
                if field is not None:
                    bean, count, coins = self._harvest(pid, index)
                    harvested.append(f"{bean} x{count} for {coins}")
            summaries.append(f"Player {pid}: {', '.join(harvested) if harvested else 'nothing'}")
        self.broadcast("Final harvest: " + "; ".join(summaries) + ".", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        coins = {pid: gs["players"][pid]["coins"] for pid in range(num_players)}
        best = max(coins.values())
        tied = [pid for pid in range(num_players) if coins[pid] == best]
        winner = tied[-1]  # the tied player furthest clockwise from the starting player (Player 0)
        standings = ", ".join(f"Player {pid}: {coins[pid]}" for pid in range(num_players))
        reason = f"{prefix} Final coins: {standings}. Player {winner} wins with {best} coins."
        if len(tied) > 1:
            reason += f" ({_join_players(tied)} tied; Player {winner} sits furthest clockwise from the starting player, Player 0, and wins the tie-break.)"
        return self.winner(winner, reason=reason)

    # ---------------------------------------------------------------- hints
    def _phase_hint(self, player_id: int) -> str:
        gs = self.game_state
        phase = gs["current_phase"]
        if phase == "plant":
            if gs["planted_from_hand"] == 0:
                return "Phase 1: plant the first card of your hand with plant <field> (or harvest <field> first to make room)."
            return "Phase 1: plant <field> plants your next card, pass stops planting, harvest <field> makes room."
        if phase == "draw_trade":
            commands = "trade <offer> for <want>, accept <id>, cancel <id>, harvest <field>, pass"
            if player_id == gs["active_player"]:
                commands += ", end trading"
            return f"Trading: use {commands}; any other text is table talk."
        if phase == "plant_mandatory":
            return f"Phase 3: plant your set-aside beans ({format_beans(gs['mandatory_plants'][player_id])}) with plant <bean> <field>, or harvest <field> to make room."
        return "The game is over."

    def _options_text(self, player_id: int) -> str:
        if self.state.done:
            return "The game is over."
        if player_id != self.state.current_player_id:
            return f"It is Player {self.state.current_player_id}'s move."
        gs = self.game_state
        phase, active = gs["current_phase"], gs["active_player"]
        player = gs["players"][player_id]
        harvestable = [
            f"field {number} ({format_field(field)}, {self._calculate_harvest_coins(*field)} coins)"
            for number, field in enumerate(player["fields"], start=1)
            if field is not None and self._harvest_error(player, number) is None
        ]
        options: List[Tuple[str, str]] = []
        if phase == "plant":
            hand = player["hand"]
            if not hand:
                header = "Your move (phase 1). Your hand is empty."
                options.append(("pass", "turn over the trading cards"))
            else:
                if gs["planted_from_hand"] == 0:
                    header = f"Your move (phase 1). You must plant the first card of your hand: {hand[0]}."
                else:
                    header = f"Your move (phase 1). You may also plant your next card, {hand[0]}, or stop."
                options.append(("plant <field>", f"{hand[0]} fits {self._fit_text(player, hand[0])}"))
                if gs["planted_from_hand"] > 0:
                    options.append(("pass", "stop planting and turn over the trading cards"))
            if harvestable:
                options.append(("harvest <field>", f"allowed now: {', '.join(harvestable)}"))
        elif phase == "draw_trade":
            pending = {trade_id: trade for trade_id, trade in gs["active_trades"].items() if trade["status"] == "pending"}
            acceptable = [
                f"#{trade_id}" for trade_id, trade in pending.items()
                if trade["proposer"] != player_id and trade["target"] in (None, player_id) and not self._missing_beans(player_id, trade["want"])
            ]
            own = [f"#{trade_id}" for trade_id, trade in pending.items() if trade["proposer"] == player_id]
            tradeable = self._tradeable_cards(player_id)
            wish = next(bean for bean in BEAN_TYPES if not tradeable or bean != tradeable[-1])
            example = f"trade 1 {tradeable[-1]} for 1 {wish}" if tradeable else f"trade nothing for 1 {wish}"
            if player_id == active:
                header = f"Your move (trading round {gs['trade_round']}). You are the active player."
                options.append(("trade <offer> for <want>", f"e.g. {example} (open to everyone), or add: with Player N"))
            else:
                header = f"Your move (trading round {gs['trade_round']}). Player {active} is the active player; you may only trade with them."
                options.append(("trade <offer> for <want>", f"e.g. {example} (offers go to Player {active}); use nothing for a gift"))
            if acceptable:
                options.append(("accept <id>", f"offers you can accept: {', '.join(acceptable)}"))
            if own:
                options.append(("cancel <id>", f"withdraw your offer: {', '.join(own)}"))
            if harvestable:
                options.append(("harvest <field>", f"allowed now: {', '.join(harvestable)}"))
            if player_id == active:
                options.append(("end trading", "stop trading; then plant the face-up cards you kept and any beans you received"))
            options.append(("pass", "give the floor to the next player"))
            options.append(("<anything else>", "is said to the whole table"))
        elif phase == "plant_mandatory":
            pending_beans = gs["mandatory_plants"][player_id]
            header = f"Your move (phase 3). Plant all of your set-aside beans, in any order: {format_beans(pending_beans)}."
            for bean in dict.fromkeys(pending_beans):
                options.append((f"plant {bean} <field>", f"{bean} fits {self._fit_text(player, bean)}"))
            if harvestable:
                options.append(("harvest <field>", f"allowed now: {', '.join(harvestable)}"))
        else:
            return "Waiting for the game to continue."
        width = max(len(command) for command, _ in options)
        return "\n".join([header] + [f"  {command:<{width}}  {description}" for command, description in options])
