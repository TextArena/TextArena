import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Poker.renderer import create_board_str


class PokerEnv(ta.GameEnv):
    min_players = 2
    max_players = 15
    mdp_includes_actions = False

    _CHECK_RE = re.compile(r"^check$", re.IGNORECASE)
    _FOLD_RE = re.compile(r"^fold$", re.IGNORECASE)
    _CALL_RE = re.compile(r"^call$", re.IGNORECASE)
    _BET_RE = re.compile(r"^bet\s+(\d+)$", re.IGNORECASE)
    _RAISE_RE = re.compile(r"^raise\s+(\d+)$", re.IGNORECASE)

    num_rounds = ta.Param(10, "The number of hands.", min=1)
    starting_chips = ta.Param(1_000, "The number of chips per player at the start.", min=1)
    small_blind = ta.Param(10, "The small blind; it may not exceed the big blind.", min=1)
    big_blind = ta.Param(20, "The big blind.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.small_blind > self.big_blind:
            raise ValueError("small_blind cannot exceed big_blind")

        self.suits = ["♠", "♥", "♦", "♣"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.rank_values = {r: i + 2 for i, r in enumerate(self.ranks)}

    def get_board_str(self, player_id: Optional[int] = None, reveal_all: bool = False):
        gs = self.state.game_state
        if player_id is None and not reveal_all:
            player_id = self.state.current_player_id
        return create_board_str(
            community_cards=gs["visible_community_cards"],
            pot=gs["pot"],
            player_chips=gs["player_chips"],
            player_hands=gs["player_hands"],
            bets=gs["player_bets"],
            viewer_id=player_id,
            reveal_all=reveal_all,
        )

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        return {
            "round": 1, "betting_round": 0, "player_chips": {pid: self.starting_chips for pid in range(num_players)}, "player_hands": {pid: [] for pid in range(num_players)},
            "community_cards": [], "visible_community_cards": [], "pot": 0, "current_bet": 0, "player_bets": {pid: 0 for pid in range(num_players)}, "button": 0, "folded_players": set(),
            "hand_contributions": {pid: 0 for pid in range(num_players)}, "hand_players": [], "all_in_players": set(), "checked_players": set(),
            "acted_players": set(), "acted_bet_levels": {}, "round_turn": 0, "game_complete": False, "last_bettor": -1, "bet_round_complete": False,
            "small_blind_player": None, "big_blind_player": None, "last_full_raise": self.big_blind,
        }

    def on_start(self):
        self.broadcast(f"Starting a {self.num_rounds}-hand Texas Hold'em game with {self.state.num_players} players.", ta.ObservationType.GAME_MESSAGE)
        self._reset_round()
        if self._is_hand_over():
            outcome = self._handle_hand_completion()
            if outcome is not None:
                self._finalize(outcome)
                return
        self.set_current_player(self._cur)

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a {self.state.num_players}-player Texas Hold'em Poker game.\nGame Information:\n"
            f"- {self.num_rounds} hands total\n- Starting stack: {self.starting_chips} chips\n- Blinds: {self.small_blind}/{self.big_blind}\n\n"
            "Available actions:\n"
            "  'Check'   - when no bet is live\n"
            "  'Call'    - match the current bet\n"
            "  'Fold'    - discard your hand\n"
            "  'Bet N'   - open for N chips\n"
            "  'Raise N' - raise by N chips (at least the previous full bet/raise unless all-in)\n"
        )

    # ------------------------------------------------------------- main hook
    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        a_type, amount = self._parse_action(action)
        if a_type == "invalid":
            return self.invalid(f"Invalid poker action. Reply with one of: {', '.join(self._options(player_id))}.")

        result = self._apply_action(player_id, a_type, amount)
        if isinstance(result, ta.Invalid):
            return result
        gs["round_turn"] += 1
        gs["bet_round_complete"] = self._is_betting_round_complete()

        outcome = self._progress_after_action(player_id)
        if outcome is not None:
            return outcome
        self.set_next_player(self._cur)
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        self.eliminate(player_id)
        self.broadcast(f"Player {player_id} was eliminated by invalid move.", ta.ObservationType.GAME_MESSAGE)
        gs = self.game_state
        gs["folded_players"].add(player_id)
        forfeited = gs["player_chips"][player_id]
        gs["hand_contributions"][player_id] += forfeited
        gs["pot"] += forfeited
        gs["player_chips"][player_id] = 0

        outcome = self._progress_after_action(player_id)
        if outcome is not None:
            return outcome
        self.set_next_player(self._cur)
        return None

    # ------------------------------------------------------------ dealing
    def _create_deck(self):
        return [{"rank": r, "suit": s} for s in self.suits for r in self.ranks]

    def _reset_round(self):
        self._eliminate_busted_players()
        gs = self.game_state
        n = self.state.num_players
        hand_players = [pid for pid in self.state.alive_players if gs["player_chips"][pid] > 0]
        gs["hand_players"] = hand_players
        for pid in range(n):
            gs["player_hands"][pid] = []

        if hand_players and gs["button"] not in hand_players:
            gs["button"] = self._next_seat(gs["button"], hand_players)

        deck = self._create_deck()
        self.rng.shuffle(deck)
        for pid in hand_players:
            gs["player_hands"][pid] = [deck.pop(), deck.pop()]

        gs["community_cards"] = [deck.pop() for _ in range(5)]
        gs["visible_community_cards"] = []
        gs["pot"] = 0
        gs["current_bet"] = 0
        gs["player_bets"] = {pid: 0 for pid in range(n)}
        gs["hand_contributions"] = {pid: 0 for pid in range(n)}
        gs["folded_players"] = set()
        gs["all_in_players"] = set()
        gs["checked_players"] = set()
        gs["acted_players"] = set()
        gs["acted_bet_levels"] = {}
        gs["round_turn"] = 0
        gs["last_bettor"] = -1
        gs["bet_round_complete"] = False
        gs["last_full_raise"] = self.big_blind

        if len(hand_players) < 2:
            gs["small_blind_player"] = None
            gs["big_blind_player"] = None
            if hand_players:
                self._cur = hand_players[0]
            return

        btn = gs["button"]
        if len(hand_players) == 2:
            sbp = btn
            bbp = self._next_seat(btn, hand_players)
            first_to_act = sbp
        else:
            sbp = self._next_seat(btn, hand_players)
            bbp = self._next_seat(sbp, hand_players)
            first_to_act = self._next_seat(bbp, hand_players)
        gs["small_blind_player"] = sbp
        gs["big_blind_player"] = bbp

        def post_blind(pid: int, amount: int):
            amt = min(amount, gs["player_chips"][pid])
            gs["player_chips"][pid] -= amt
            gs["player_bets"][pid] += amt
            gs["hand_contributions"][pid] += amt
            gs["pot"] += amt
            if gs["player_chips"][pid] == 0:
                gs["all_in_players"].add(pid)
            return amt

        post_blind(sbp, self.small_blind)
        post_blind(bbp, self.big_blind)
        # A short all-in big blind does not lower the pre-flop bring-in.
        gs["current_bet"] = self.big_blind
        first_actor = self._first_required_actor_from(first_to_act)
        self._cur = first_actor if first_actor is not None else first_to_act

    def render(self, player_id: int) -> str:
        """The table as seen by `player_id`: only their own hole cards, plus their legal options."""
        gs = self.game_state
        n = self.state.num_players
        comm = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["visible_community_cards"])
        betting_round_names = {0: "Pre‑flop", 1: "Flop", 2: "Turn", 3: "River"}
        btn = gs["button"]
        sb = gs["small_blind_player"]
        bb = gs["big_blind_player"]
        lines = []
        for pid in range(n):
            roles = []
            if pid == btn: roles.append("Dealer")
            if pid == sb: roles.append("SB")
            if pid == bb: roles.append("BB")
            role_txt = f" ({'/'.join(roles)})" if roles else ""
            if not self.state.is_player_alive(pid): status = "eliminated"
            elif pid not in gs["hand_players"]: status = "sitting out"
            elif pid in gs["folded_players"]: status = "folded"
            elif pid in gs["all_in_players"]: status = "all-in"
            else: status = "active"
            lines.append(f"P{pid}{role_txt}: {gs['player_chips'][pid]} chips | bet {gs['player_bets'][pid]} | {status}")

        hole = gs["player_hands"].get(player_id, [])
        hole_text = ", ".join(f"{card['rank']}{card['suit']}" for card in hole) if hole else "(not dealt)"
        msg = (
            f"===== Hand {gs['round']} / {self.num_rounds} - {betting_round_names[gs['betting_round']]} =====\n"
            f"Pot: {gs['pot']} | Current bet: {gs['current_bet']}\nVisible board: [{comm}]\n" + "\n".join(lines) +
            f"\nYour hole: {hole_text}\n"
            "=============================================="
        )
        if not self.state.done and self._can_act(player_id):
            due = max(0, gs["current_bet"] - gs["player_bets"][player_id])
            msg += f"\nTo call: {due} | Your options: {', '.join(self._options(player_id))}"
        return msg

    def _options(self, pid: int) -> List[str]:
        """Legal commands for `pid`, with the amounts `_apply_action` accepts."""
        gs = self.game_state
        chips, committed, current = gs["player_chips"][pid], gs["player_bets"][pid], gs["current_bet"]
        due = current - committed
        options = ["'fold'"] if due > 0 else ["'check'"]
        if due > 0:
            options.append(f"'call' ({min(due, chips)} chips{', all-in' if due >= chips else ''})")

        stack_total = committed + chips
        if current == 0:
            verb, low_total = "bet", self.big_blind
        else:
            reopened = (
                pid not in gs["acted_players"]
                or current - gs["acted_bet_levels"].get(pid, current) >= gs["last_full_raise"]
            )
            if not reopened or stack_total <= current:
                return options
            verb = "raise"
            low_total = self.big_blind if current < self.big_blind else current + gs["last_full_raise"]
        low, high = low_total - current, stack_total - current
        if low < high:
            options.append(f"'{verb} N' (N from {low} to {high}; {high} is all-in)")
        else:
            options.append(f"'{verb} {high}' (all-in)")
        return options

    # ----------------------------------------------------------- turn logic
    def _progress_after_action(self, player_id: int) -> Optional[ta.Outcome]:
        if self._is_hand_over():
            return self._handle_hand_completion()
        if self._is_betting_round_complete():
            return self._advance_game_phase()

        next_pid = self._next_required_actor(player_id)
        if next_pid is None:
            return self._advance_game_phase()
        self._cur = next_pid
        return None

    def _can_act(self, pid: int) -> bool:
        gs = self.game_state
        return (
            pid in gs["hand_players"]
            and self.state.is_player_alive(pid)
            and pid not in gs["folded_players"]
            and pid not in gs["all_in_players"]
            and gs["player_chips"][pid] > 0
        )

    def _requires_action(self, pid: int) -> bool:
        gs = self.game_state
        return self._can_act(pid) and (
            pid not in gs["acted_players"] or gs["player_bets"][pid] != gs["current_bet"]
        )

    def _next_required_actor(self, after: int) -> Optional[int]:
        n = self.state.num_players
        for offset in range(1, n + 1):
            pid = (after + offset) % n
            if self._requires_action(pid):
                return pid
        return None

    def _first_required_actor_from(self, start: int) -> Optional[int]:
        n = self.state.num_players
        for offset in range(n):
            pid = (start + offset) % n
            if self._requires_action(pid):
                return pid
        return None

    def _next_seat(self, after: int, players: List[int]) -> int:
        player_set = set(players)
        for offset in range(1, self.state.num_players + 1):
            pid = (after + offset) % self.state.num_players
            if pid in player_set:
                return pid
        raise ValueError("No player is available for seat rotation.")

    def _check_and_eliminate(self, pid: int):
        """Mark a zero-stack player as all-in; eliminate later if they stay broke."""
        if self.game_state["player_chips"][pid] == 0:
            self.game_state["all_in_players"].add(pid)

    def _parse_action(self, action: str) -> Tuple[str, Optional[int]]:
        if self._CHECK_RE.search(action):                       return "check", None
        if self._FOLD_RE.search(action):                        return "fold", None
        if self._CALL_RE.search(action):                        return "call", None
        try:
            if (m := self._BET_RE.search(action)) is not None:
                token = m.group(1)
                return ("invalid", None) if len(token) > 100 else ("bet", int(token))
            if (m := self._RAISE_RE.search(action)) is not None:
                token = m.group(1)
                return ("invalid", None) if len(token) > 100 else ("raise", int(token))
        except ValueError:
            return "invalid", None
        return "invalid", None

    def _apply_action(self, pid: int, a_type: str, bet_amt: Optional[int]) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state

        if not self._can_act(pid):
            return self.invalid("This player is not eligible to act.")

        def pay(player: int, chips: int):
            gs["player_chips"][player] -= chips
            gs["player_bets"][player] += chips
            gs["hand_contributions"][player] += chips
            gs["pot"] += chips
            self._check_and_eliminate(player)

        if a_type == "fold":
            gs["folded_players"].add(pid)
            gs["acted_players"].add(pid)
            gs["acted_bet_levels"][pid] = gs["current_bet"]
            self.broadcast(f"Player {pid} folds.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return None

        if a_type == "check":
            if gs["current_bet"] > gs["player_bets"][pid]:
                return self.invalid("Cannot check facing a bet.")
            gs["checked_players"].add(pid)
            gs["acted_players"].add(pid)
            gs["acted_bet_levels"][pid] = gs["current_bet"]
            self.broadcast(f"Player {pid} checks.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return None

        if a_type == "call":
            due = gs["current_bet"] - gs["player_bets"][pid]
            if due <= 0:
                gs["checked_players"].add(pid)
                gs["acted_players"].add(pid)
                gs["acted_bet_levels"][pid] = gs["current_bet"]
                self.broadcast(
                    f"Player {pid} calls with nothing due (checks).",
                    ta.ObservationType.GAME_ACTION_DESCRIPTION,
                )
                return None
            pay_amount = min(due, gs["player_chips"][pid])
            pay(pid, pay_amount)
            gs["acted_players"].add(pid)
            gs["acted_bet_levels"][pid] = gs["current_bet"]
            if pay_amount < due:
                gs["all_in_players"].add(pid)
            self.broadcast(f"Player {pid} calls {pay_amount}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return None

        if bet_amt is None or bet_amt <= 0:
            return self.invalid("Bet and raise amounts must be positive.")

        cur_contrib = gs["player_bets"][pid]
        if a_type == "bet":
            if gs["current_bet"] > 0:
                return self.invalid("Cannot bet facing a live bet; use call or raise.")
            requested_total = bet_amt
        else:
            if gs["current_bet"] == 0:
                return self.invalid("Cannot raise without a live bet; use bet.")
            last_action_level = gs["acted_bet_levels"].get(pid, gs["current_bet"])
            if (
                pid in gs["acted_players"]
                and gs["current_bet"] - last_action_level < gs["last_full_raise"]
            ):
                return self.invalid("A short all-in did not reopen raising for this player.")
            requested_total = gs["current_bet"] + bet_amt

        stack_total = cur_contrib + gs["player_chips"][pid]
        actual_total = min(requested_total, stack_total)
        previous_bet = gs["current_bet"]
        if actual_total <= previous_bet:
            return self.invalid(f"You cannot raise: your stack only covers a call. Reply with one of: {', '.join(self._options(pid))}.")

        is_all_in = actual_total == stack_total
        if a_type == "bet":
            full_raise = actual_total >= self.big_blind
        else:
            minimum_total = (
                self.big_blind
                if previous_bet < self.big_blind
                else previous_bet + gs["last_full_raise"]
            )
            full_raise = actual_total >= minimum_total
        if not full_raise and not is_all_in:
            all_in = stack_total - previous_bet
            if a_type == "bet":
                rule = f"A bet must be at least {self.big_blind} chips"
                low = self.big_blind
            else:
                low = minimum_total - previous_bet
                rule = f"A raise must add at least {low} chips (a total bet of at least {minimum_total})"
            if low < all_in:
                return self.invalid(f"{rule}: reply '{a_type} {low}' or more.")
            return self.invalid(f"{rule}, and only an all-in may be smaller; your stack allows only '{a_type} {all_in}' (all-in).")

        needed = actual_total - cur_contrib
        gs["bet_round_complete"] = False
        pay(pid, needed)
        gs["current_bet"] = gs["player_bets"][pid]
        gs["last_bettor"] = pid
        if a_type == "bet":
            if full_raise:
                gs["last_full_raise"] = actual_total
            # Even a short opening all-in changes checked players' options.
            gs["acted_players"] = {pid}
            gs["acted_bet_levels"] = {pid: actual_total}
        elif full_raise:
            if previous_bet >= self.big_blind:
                gs["last_full_raise"] = actual_total - previous_bet
            else:
                gs["last_full_raise"] = self.big_blind
            gs["acted_players"] = {pid}
            gs["acted_bet_levels"] = {pid: actual_total}
        else:
            # A short all-in must be called, but does not reopen prior action.
            gs["acted_players"].add(pid)
            gs["acted_bet_levels"][pid] = actual_total
        gs["checked_players"] = set()
        verb = "bets" if a_type == "bet" else "raises"
        self.broadcast(f"Player {pid} {verb} to {gs['player_bets'][pid]}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def _get_first_active_player_of_round(self) -> Optional[int]:
        gs = self.game_state
        if gs["betting_round"] == 0:
            if len(gs["hand_players"]) == 2:
                first_seat = gs["small_blind_player"]
            else:
                first_seat = self._next_seat(gs["big_blind_player"], gs["hand_players"])
        else:
            first_seat = self._next_seat(gs["button"], gs["hand_players"])
        return self._first_required_actor_from(first_seat)

    def _is_hand_over(self) -> bool:
        gs = self.game_state
        contenders = [
            pid
            for pid in gs["hand_players"]
            if self.state.is_player_alive(pid) and pid not in gs["folded_players"]
        ]
        if len(contenders) <= 1:
            return True
        actors = [pid for pid in contenders if self._can_act(pid)]
        if not actors:
            return True
        if len(actors) == 1:
            # current_bet can exceed every contender's bet when the big blind is a short all-in.
            lone_actor = actors[0]
            return gs["player_bets"][lone_actor] >= max(gs["player_bets"][pid] for pid in contenders)
        return False

    def _is_betting_round_complete(self):
        gs = self.game_state
        actors = [pid for pid in gs["hand_players"] if self._can_act(pid)]
        return all(
            pid in gs["acted_players"] and gs["player_bets"][pid] == gs["current_bet"]
            for pid in actors
        )

    # --------------------------------------------------------- hand endings
    def _advance_game_phase(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if gs["betting_round"] < 3:
            gs["betting_round"] += 1
            gs["current_bet"] = 0
            gs["player_bets"] = {pid: 0 for pid in range(self.state.num_players)}
            gs["checked_players"] = set()
            gs["acted_players"] = set()
            gs["acted_bet_levels"] = {}
            gs["last_bettor"] = -1
            gs["bet_round_complete"] = False
            gs["last_full_raise"] = self.big_blind

            if gs["betting_round"] == 1:    gs["visible_community_cards"] = gs["community_cards"][:3]
            elif gs["betting_round"] == 2:  gs["visible_community_cards"] = gs["community_cards"][:4]
            elif gs["betting_round"] == 3:  gs["visible_community_cards"] = gs["community_cards"][:5]

            first_actor = self._get_first_active_player_of_round()
            if first_actor is None:
                return self._handle_hand_completion()
            self._cur = first_actor
            return None
        # all betting rounds finished → showdown
        self._handle_showdown()
        return self._handle_post_hand_or_game_end()

    def _eliminate_busted_players(self):
        gs = self.game_state
        for pid, chips in gs["player_chips"].items():
            if chips == 0 and self.state.is_player_alive(pid):
                self.eliminate(pid)

    def _handle_hand_completion(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        contenders = [
            pid
            for pid in gs["hand_players"]
            if self.state.is_player_alive(pid) and pid not in gs["folded_players"]
        ]
        # Run out the board only for a real showdown. A fold must not reveal
        # community cards that were never reached in public play.
        if len(contenders) > 1:
            gs["visible_community_cards"] = gs["community_cards"]
        self._handle_showdown()
        return self._handle_post_hand_or_game_end()

    def _handle_post_hand_or_game_end(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        alive = list(self.state.alive_players)
        if len(alive) <= 1 or gs["round"] >= self.num_rounds:
            gs["game_complete"] = True
            return self._final_outcome()
        gs["round"] += 1
        gs["betting_round"] = 0
        gs["button"] = self._next_seat(gs["button"], alive)
        self._reset_round()
        if self._is_hand_over():
            return self._handle_hand_completion()
        return None

    def _handle_showdown(self):
        gs = self.game_state
        active = [
            pid
            for pid in gs["hand_players"]
            if self.state.is_player_alive(pid) and pid not in gs["folded_players"]
        ]
        if not active:
            raise RuntimeError("Poker hand ended without an eligible player.")

        reveal = []
        scores = {}
        if len(active) > 1:
            for pid in active:
                hand = gs["player_hands"][pid]
                reveal.append(f"Player {pid}: {hand[0]['rank']}{hand[0]['suit']} {hand[1]['rank']}{hand[1]['suit']}")
                scores[pid] = self._evaluate_hand(hand + gs["community_cards"])
            community_cards = ", ".join(f'{card["rank"]}{card["suit"]}' for card in gs["community_cards"])
            self.broadcast(
                f"Showdown round {gs['round']}:\n" + "\n".join(reveal) + f"\nCommunity cards: {community_cards}",
                ta.ObservationType.GAME_MESSAGE,
            )

        contributions = gs["hand_contributions"]
        contribution_total = sum(contributions.values())
        if contribution_total != gs["pot"]:
            raise RuntimeError(
                f"Poker pot invariant failed: pot={gs['pot']}, contributions={contribution_total}."
            )

        # One pot per contribution level, merging levels that the same players can win: a folded
        # player's smaller contribution does not start a side pot, only an all-in does.
        pots = []  # [amount, eligible players, contributors]
        previous = 0
        for level in sorted({amount for amount in contributions.values() if amount > 0}):
            contributors = {pid for pid, amount in contributions.items() if amount >= level}
            amount = (level - previous) * len(contributors)
            previous = level
            eligible = [pid for pid in active if contributions[pid] >= level]
            if not eligible:
                # This can only arise after a mid-hand administrative elimination.
                # Its chips remain dead money and go to the best remaining hand.
                eligible = list(active)
            uncalled = len(active) > 1 and len(contributors) == 1 and contributors == set(eligible)
            if pots and pots[-1][1] == eligible and not uncalled:
                pots[-1][0] += amount
                pots[-1][2] |= contributors
            else:
                pots.append([amount, eligible, contributors])
        if len(pots) > 1 and pots[-1][2] == set(pots[-1][1]) == {pots[-1][1][0]}:
            amount, (bettor,), _ = pots.pop()
            gs["player_chips"][bettor] += amount
            self.broadcast(f"Player {bettor}'s uncalled {amount} chips are returned.", ta.ObservationType.GAME_MESSAGE)
        for pot_index, (amount, eligible, _) in enumerate(pots):
            if len(eligible) == 1:
                winners = eligible
            else:
                best_score = max(scores[pid] for pid in eligible)
                winners = [pid for pid in eligible if scores[pid] == best_score]
            pot_name = "the pot" if len(pots) == 1 else "the main pot" if pot_index == 0 else f"side pot {pot_index}"
            self._award_pot(amount, winners, pot_name)

        gs["pot"] = 0
        self._eliminate_busted_players()

    def _award_pot(self, amount: int, winners: List[int], pot_name: str):
        gs = self.game_state
        ordered_winners = sorted(
            winners,
            key=lambda pid: (pid - gs["button"] - 1) % self.state.num_players,
        )
        share, remainder = divmod(amount, len(ordered_winners))
        for index, winner in enumerate(ordered_winners):
            gs["player_chips"][winner] += share + (1 if index < remainder else 0)
        if len(ordered_winners) == 1:
            message = f"Player {ordered_winners[0]} wins {pot_name} of {amount} chips."
        else:
            names = ", ".join(map(str, ordered_winners[:-1])) + f" and {ordered_winners[-1]}"
            message = (
                f"Players {names} split {pot_name} of {amount} chips "
                f"({share} each; {remainder} odd chip(s) awarded left of the button)."
            )
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    # --------------------------------------------------------- hand ranking
    def _evaluate_hand(self, cards: List[Dict[str, str]]) -> Tuple[int, List[int]]:
        """Return (category_rank, tiebreak_list).  Higher tuple wins."""
        ranks = [self.rank_values[c["rank"]] for c in cards]
        suits = [c["suit"] for c in cards]
        r_counter = Counter(ranks)
        s_counter = Counter(suits)

        # Flush?
        flush_suit = next((s for s, cnt in s_counter.items() if cnt >= 5), None)
        distinct = sorted(set(ranks))
        straight, straight_hi = self._check_straight(distinct)

        # 9  Straight flush
        if flush_suit and straight:
            flush_cards = sorted({r for r, s in zip(ranks, suits) if s == flush_suit})
            sf, sf_hi = self._check_straight(flush_cards)
            if sf: return 9, [sf_hi]

        # 8  Quads
        if 4 in r_counter.values():
            quad = max(r for r, c in r_counter.items() if c == 4)
            kicker = max(r for r in ranks if r != quad)
            return 8, [quad, kicker]

        # 7  Full house
        if 3 in r_counter.values():
            triple = max(r for r, c in r_counter.items() if c == 3)
            pair_candidates = [r for r, c in r_counter.items() if c >= 2 and r != triple]
            if pair_candidates:
                pair = max(pair_candidates)
                return 7, [triple, pair]

        # 6  Flush
        if flush_suit:
            flush_cards = sorted((r for r, s in zip(ranks, suits) if s == flush_suit), reverse=True)
            return 6, flush_cards[:5]

        # 5  Straight
        if straight:
            return 5, [straight_hi]

        # 4  Trips
        if 3 in r_counter.values():
            triple = max(r for r, c in r_counter.items() if c == 3)
            kickers = sorted((r for r in ranks if r != triple), reverse=True)
            return 4, [triple] + kickers[:2]

        # 3  Two-pair
        pairs = [r for r, c in r_counter.items() if c == 2]
        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            top_pairs = pairs[:2]
            kicker = max(r for r in ranks if r not in top_pairs)
            return 3, top_pairs + [kicker]

        # 2  One-pair
        if len(pairs) == 1:
            p = pairs[0]
            kickers = sorted((r for r in ranks if r != p), reverse=True)
            return 2, [p] + kickers[:3]

        # 1  High card
        return 1, sorted(ranks, reverse=True)[:5]

    def _check_straight(self, sorted_ranks: List[int]) -> Tuple[bool, int]:
        if len(sorted_ranks) < 5:
            return False, -1
        for i in range(len(sorted_ranks) - 5, -1, -1):
            seq = sorted_ranks[i:i + 5]
            if seq[-1] - seq[0] == 4:
                return True, seq[-1]
        if {14, 2, 3, 4, 5}.issubset(sorted_ranks):
            return True, 5
        return False, -1

    def _final_outcome(self) -> ta.Outcome:
        """Assign zero-sum rank rewards in [-1, 1], averaging tied places."""
        chips = self.game_state["player_chips"]
        stack_levels = sorted(set(chips.values()))
        num_players = len(chips)
        if len(stack_levels) == 1 or num_players == 1:
            rewards = {pid: 0.0 for pid in chips}
        else:
            reward_by_stack = {}
            first_place = 0
            for stack in stack_levels:
                tied_count = sum(value == stack for value in chips.values())
                last_place = first_place + tied_count - 1
                average_place = (first_place + last_place) / 2
                reward_by_stack[stack] = -1.0 + 2.0 * average_place / (num_players - 1)
                first_place = last_place + 1
            rewards = {pid: reward_by_stack[stack] for pid, stack in chips.items()}
        winners = [pid for pid, stack in chips.items() if stack == stack_levels[-1]]
        if len(winners) == 1:
            leader = f"Player {winners[0]} wins with the most chips."
        else:
            leader = f"Players {', '.join(map(str, winners[:-1]))} and {winners[-1]} tie for the most chips."
        standings = ", ".join(f"Player {pid} {chips[pid]}" for pid in sorted(chips, key=lambda pid: -chips[pid]))
        return self.outcome(rewards, reason=f"{leader} Final chip counts: {standings}.")
