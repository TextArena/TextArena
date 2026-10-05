import re
from typing import Any, Dict, Optional, Union

import textarena as ta
# from textarena.envs.IndianPoker.renderer import create_board_str # TODO


class IndianPokerEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    ante = 1
    max_rounds = ta.Param(1, "The number of rounds in the match.", min=1)
    starting_chips = ta.Param(100, "The number of chips each player starts with.", min=1)

    @staticmethod
    def _rank(card: int) -> int: return (card % 13) + 2 # 0-51 → 2-14
    @staticmethod
    def _rank_to_str(card: int) -> str: return ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"][(card % 13)]
    # def get_board_str(self): return create_board_str(self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        return {"player_chips": {0: self.starting_chips, 1: self.starting_chips}, "current_round": 0, "starting_player": 0}

    def on_start(self):
        self._init_round()  # never ends the game here (current_round starts at 0)
        self.set_current_player(self.game_state["starting_player"])  # round 1 starts with player 1

    def _init_round(self) -> Optional[ta.Outcome]:
        gs = self.game_state

        # check if match finished
        if gs["current_round"] >= self.max_rounds:
            return self._declare_match_winner("Completed all rounds")
        if any(gs["player_chips"][pid] < self.ante for pid in (0, 1)):
            return self._declare_match_winner("A player cannot cover the ante")
        gs["current_round"] += 1

        deck = list(range(52))
        self.rng.shuffle(deck)
        gs["player_cards"] = {0: deck[0], 1: deck[1]}

        gs["pot"] = self.ante * 2
        for pid in (0, 1): gs["player_chips"][pid] -= self.ante

        # per-round betting bookkeeping
        gs["current_bets"] = {0: 0, 1: 0} # chips committed this round
        gs["highest_bet"] = 0 # current bet to match
        gs["prev_action"] = None # track check-check
        gs["second_check"] = False

        # rotate first player
        gs["starting_player"] = 1 - gs["starting_player"]
        for pid in (0, 1):
            self.message(pid, f"### Round {gs['current_round']}/{self.max_rounds}\nYour opponent's card is: {self._rank_to_str(gs['player_cards'][1-pid])}", ta.ObservationType.GAME_MESSAGE)
        return None

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a game of Indian Poker.\n- 52-card deck; you see only the opponent's card.\n- Ante {self.ante} chip(s) each round, {self.max_rounds} round(s) total.\n"
            f"- Valid moves: 'check'  |  'bet X'  |  'call'  |  'raise X'  |  'fold'  (X is a positive integer <= your chip count.)\n- Highest hidden card wins the pot at showdown.\n"
            f"- Both players start with {self.starting_chips} chips. 'raise X' adds X chips on top of the bet you face; a bet or raise "
            f"can never exceed what your opponent has left to call it. There is no limit on the number of raises.\n"
            f"- Cards rank 2 (low) to A (high); suits do not matter and equal ranks split the pot.\n"
            f"- After {self.max_rounds} round(s), or as soon as a player cannot pay the ante, the player with more chips wins.\n"
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        opponent = 1 - player_id
        lines = [
            f"Round {gs['current_round']} of {self.max_rounds}",
            f"Opponent's card: {self._rank_to_str(gs['player_cards'][opponent])} | Your card: hidden",
            f"Pot: {gs['pot']} | Your chips: {gs['player_chips'][player_id]} | Opponent chips: {gs['player_chips'][opponent]}",
            f"Chips bet this round - you: {gs['current_bets'][player_id]}, opponent: {gs['current_bets'][opponent]}",
        ]
        if not self.state.done:
            lines.append(f"Your possible actions: {self._legal_actions(player_id)}")
        return "\n".join(lines)

    def _find_token(self, msg: str):
        patterns = [
            ("check", re.compile(r"^check$", re.I)),
            ("fold", re.compile(r"^fold$", re.I)),
            ("call", re.compile(r"^call$", re.I)),
            ("bet", re.compile(r"^bet\s+(\d+)$", re.I)),
            ("raise", re.compile(r"^raise\s+(\d+)$", re.I)),
        ]
        found = [(name, m) for name, rx in patterns if (m := rx.match(msg))]
        if len(found) != 1: return None, None # none or ambiguous
        name, match = found[0]
        try:
            amt = int(match.group(1)) if name in ("bet", "raise") else None
        except ValueError:
            return None, None
        return name, amt

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        pid = player_id
        gs = self.game_state

        move, amount = self._find_token(action)
        if move is None:
            return self.invalid("Supply exactly ONE action, e.g. 'check', 'bet 2', 'call', 'raise 3', or 'fold'.")

        to_call = gs["highest_bet"] - gs["current_bets"][pid]

        # legality checks
        if move == "check" and to_call != 0:            return self.invalid("Cannot 'check' - you are facing a bet.")
        if move in ("bet", "raise") and amount <= 0:    return self.invalid("Bet / Raise amount must be ≥ 1.")
        if move == "bet" and to_call != 0:              return self.invalid("Cannot 'bet' - must 'call' / 'raise' / 'fold'.")
        if move == "call" and to_call == 0:             return self.invalid("Nothing to call; you may 'check' instead.")
        if move == "raise" and to_call == 0:            return self.invalid("Use 'bet X' to open; there is no bet to raise.")
        if move == "fold" and to_call == 0:             return self.invalid("Cannot fold when there is no bet to call.")

        # bankroll check
        cost = 0
        if move == "bet":       cost = amount
        elif move == "call":    cost = to_call
        elif move == "raise":   cost = to_call + amount

        if cost > gs["player_chips"][pid]:              return self.invalid("Insufficient chips for that action.")
        if move in ("bet", "raise") and amount > gs["player_chips"][1 - pid]:
            return self.invalid("Bet exceeds the effective stack available to both players.")

        outcome = None
        round_ended = False
        self.broadcast(f"Player {pid} -> {move}{' ' + str(amount) if amount else ''}", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if move == "check":
            gs["prev_action"] = "check"
            if gs.get("second_check"): # second consecutive check -> showdown
                outcome = self._showdown()
                round_ended = True
            else:
                gs["second_check"] = True

        elif move == "bet":
            gs["second_check"] = False
            gs["highest_bet"] = amount
            gs["current_bets"][pid] += amount
            gs["player_chips"][pid] -= amount
            gs["pot"] += amount
            gs["prev_action"] = "bet"

        elif move == "call":
            gs["second_check"] = False
            gs["current_bets"][pid] += to_call
            gs["player_chips"][pid] -= to_call
            gs["pot"] += to_call
            outcome = self._showdown()
            round_ended = True

        elif move == "raise":
            gs["second_check"] = False
            new_bet = gs["highest_bet"] + amount
            chips_needed = new_bet - gs["current_bets"][pid]
            gs["highest_bet"] = new_bet
            gs["current_bets"][pid] += chips_needed
            gs["player_chips"][pid] -= chips_needed
            gs["pot"] += chips_needed
            gs["prev_action"] = "raise"

        elif move == "fold":
            outcome = self._end_round(1 - pid, f"Player {pid} folded.")
            round_ended = True

        if round_ended:
            if outcome is not None:
                return outcome
            self.set_next_player(gs["starting_player"])  # new round: its starter acts next
        return None  # otherwise the round continues with the other player

    def _legal_actions(self, pid: int) -> str:
        gs = self.game_state
        to_call = gs["highest_bet"] - gs["current_bets"][pid]
        if to_call == 0:
            legal = "'check'"
            max_bet = min(gs["player_chips"][pid], gs["player_chips"][1 - pid])
            if max_bet > 0:
                legal += f", 'bet X' (X from 1 to {max_bet})"
        else:
            legal = f"'call' (cost {to_call}), 'fold'"
            max_raise = min(gs["player_chips"][pid] - to_call, gs["player_chips"][1 - pid])
            if max_raise > 0:
                legal += f", 'raise X' (X from 1 to {max_raise})"
        return legal

    def _end_round(self, winner: int, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        pot = gs["pot"]
        gs["player_chips"][winner] += pot
        gs["pot"] = 0
        self.broadcast(f"{reason}  Pot {pot} → Player {winner}. (Bankrolls P0:{gs['player_chips'][0]}, P1:{gs['player_chips'][1]})", ta.ObservationType.GAME_MESSAGE)
        return self._init_round()

    def _showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        c0, c1 = gs["player_cards"][0], gs["player_cards"][1]
        r0, r1 = self._rank(c0), self._rank(c1)

        if r0 > r1:     return self._end_round(0, f"Showdown: {self._rank_to_str(c0)} beats {self._rank_to_str(c1)}.")
        elif r1 > r0:   return self._end_round(1, f"Showdown: {self._rank_to_str(c1)} beats {self._rank_to_str(c0)}.")
        else:  # tie – split pot
            split = gs["pot"] // 2
            gs["player_chips"][0] += split
            gs["player_chips"][1] += gs["pot"] - split
            gs["pot"] = 0
            self.broadcast(f"Showdown tie: both {self._rank_to_str(c0)}. Pot split – each receives {split}.", ta.ObservationType.GAME_MESSAGE)
            return self._init_round()

    def _declare_match_winner(self, reason: str) -> ta.Outcome:
        bank0, bank1 = self.game_state["player_chips"].values()
        if bank0 > bank1:
            return self.winner(0, f"{reason}: Player 0 wins ({bank0} > {bank1})")
        if bank1 > bank0:
            return self.winner(1, f"{reason}: Player 1 wins ({bank1} > {bank0})")
        return self.draw(f"{reason}: equal chips")
