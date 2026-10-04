import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta


class LeducHoldemEnv(ta.GameEnv):
    """
    Two-player Leduc Hold’em (6-card deck: JJQQKK in 2 suits).
    • Ante 1 chip -> each gets 1 private card.
    • Pre-flop betting (check/bet/raise/call/fold; fixed bet = 2 chips, max 2 raises).
    • Reveal one public card -> second betting round (bet = 4 chips).
    • Showdown: pair > high card; ties split pot.
    """
    min_players = 2
    max_players = 2

    def __init__(self, starting_bank: int = 100, max_rounds: int = 5):
        if not isinstance(starting_bank, int) or isinstance(starting_bank, bool) or starting_bank < 1:
            raise ValueError("starting_bank must be a positive integer")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer")
        self.starting_bank = starting_bank
        self.deck = [r for r in range(3) for _ in range(2)] # deck = two of each rank 0-2  (0=J, 1=Q, 2=K)
        self.bet_sizes = [2, 4] # round-0 / round-1 fixed bet
        self.max_rounds = max_rounds
        self.action_space = re.compile(r"^\s*\[?\s*(check|call|bet|raise|fold)\s*\]?\s*$", re.I)

    @staticmethod
    def _rank_to_str(r: int) -> str: return ["J", "Q", "K"][r]

    def _legal(self, gs, pid): # returns set of legal strings
        bet_unit = self.bet_sizes[gs["round"]]
        if gs["current_bet"] == 0:
            legal = {"check"}
            if self._can_reach_target(gs, pid, bet_unit):
                legal.add("bet")
            return legal

        legal = {"fold"}
        to_call = gs["current_bet"] - gs["round_bets"][pid]
        if to_call <= gs["player_bank"][pid]:
            legal.add("call")
        next_target = gs["current_bet"] + bet_unit
        if gs["raises_this_round"] < 2 and self._can_reach_target(gs, pid, next_target):
            legal.add("raise")
        return legal

    def _can_reach_target(self, gs, pid: int, target: int) -> bool:
        """Both heads-up players must be able to cover a fixed-limit target."""
        opponent = 1 - pid
        actor_cost = target - gs["round_bets"][pid]
        opponent_cost = target - gs["round_bets"][opponent]
        return actor_cost <= gs["player_bank"][pid] and opponent_cost <= gs["player_bank"][opponent]

    def setup(self) -> Dict[str, Any]:
        return {"round": 0, "pot": 0, "player_bank": {0: self.starting_bank, 1: self.starting_bank}, "player_cards": {}, "board_card": None, "board_revealed": False, "current_bet": 0, "round_bets": {0: 0, 1: 0}, "raises_this_round": 0, "starting_player": 0}

    def on_start(self):
        self._deal_new_hand()  # cannot end the game on the very first hand
        self.set_current_player(self.game_state["starting_player"])  # hand 1 starts with player 1

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Leduc Hold'em.\nRespond with one action token like 'check', 'bet', 'call', 'raise', or 'fold' when it is your turn.\n"
            f"Fixed bet sizes: 2 chips pre-flop, 4 chips post-flop (max 2 raises per round)."
        )

    def _deal_new_hand(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        # check if we have reached the round limit
        if gs.get("hands_dealt", 0) >= self.max_rounds:
            return self._declare_match_winner("Reached hand limit")
        if any(bank < 1 for bank in gs["player_bank"].values()):
            return self._declare_match_winner("A player cannot cover the ante")
        gs["hands_dealt"] = gs.get("hands_dealt", 0) + 1

        gs.update({"round": 0, "pot": 2, "current_bet": 0, "round_bets": {0: 0, 1: 0}, "raises_this_round": 0, "prev_check": False, "board_revealed": False})
        for pid in (0, 1): gs["player_bank"][pid] -= 1
        deck = self.deck.copy()
        self.rng.shuffle(deck)
        gs["player_cards"] = {0: deck.pop(), 1: deck.pop()}
        gs["board_card"] = deck.pop()

        # alternate first player
        gs["starting_player"] ^= 1

        # private observations
        for pid in (0, 1): self.message(pid, f"### New hand - your private card: {self._rank_to_str(gs['player_cards'][pid])}", ta.ObservationType.GAME_MESSAGE)
        self._announce_legal(gs["starting_player"])
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        pid = player_id
        gs = self.game_state
        m = self.action_space.match(action)
        if not m:
            return self.invalid("Supply exactly one legal action token.")

        move = m.group(1).lower()
        legal = self._legal(gs, pid)
        if move not in legal:
            return self.invalid(f"Illegal now. Allowed: {legal}")

        bet_unit = self.bet_sizes[gs["round"]]

        if move == "check":
            if gs.get("prev_check"):
                return self._finish_betting_round()
            gs["prev_check"] = True
            self.broadcast(f"Player {pid} checks.", ta.ObservationType.GAME_MESSAGE)
            self._announce_legal(1 - pid)
            return None
        gs["prev_check"] = False

        if move == "bet":
            gs["current_bet"] = bet_unit
            gs["raises_this_round"] = 0
            self._commit_chips(pid, gs["current_bet"] - gs["round_bets"][pid])
            self.broadcast(f"Player {pid} bets {bet_unit}.", ta.ObservationType.GAME_MESSAGE)
        elif move == "raise":
            gs["raises_this_round"] += 1
            gs["current_bet"] += bet_unit
            self._commit_chips(pid, gs["current_bet"] - gs["round_bets"][pid])
            self.broadcast(f"Player {pid} raises {bet_unit}.", ta.ObservationType.GAME_MESSAGE)
        elif move == "call":
            to_call = gs["current_bet"] - gs["round_bets"][pid]
            self._commit_chips(pid, to_call)
            self.broadcast(f"Player {pid} calls {to_call}.", ta.ObservationType.GAME_MESSAGE)
            return self._finish_betting_round()
        elif move == "fold":
            return self._finish_hand(self._award(1 - pid, reason=f"Player {pid} folds."))

        # continue betting
        self._announce_legal(1 - pid)
        return None

    def _finish_betting_round(self) -> Optional[ta.Outcome]:
        return self._finish_hand(self._next_round_or_showdown())

    def _finish_hand(self, outcome: Optional[ta.Outcome]) -> Optional[ta.Outcome]:
        if outcome is not None:
            return outcome
        self.set_next_player(self.game_state["starting_player"])  # flop or new hand: its starter acts next
        return None

    def _commit_chips(self, pid: int, amount: int):
        gs = self.game_state
        gs["player_bank"][pid] -= amount
        gs["round_bets"][pid] += amount
        gs["pot"] += amount

    def _announce_legal(self, to_pid: int):
        legal = ", ".join(f"'{a}'" for a in sorted(self._legal(self.game_state, to_pid)))
        self.message(to_pid, f"Valid actions: {legal}", ta.ObservationType.GAME_BOARD)

    def _next_round_or_showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if gs["round"] == 0:                   # flop round begins
            gs.update({"round": 1, "current_bet": 0, "round_bets": {0: 0, 1: 0}, "raises_this_round": 0, "prev_check": False, "board_revealed": True})
            card = self._rank_to_str(gs["board_card"])
            self.broadcast(f"Flop card revealed: {card}", ta.ObservationType.GAME_MESSAGE)
            self._announce_legal(gs["starting_player"])
            return None
        else:
            return self._showdown()

    def _rank_strength(self, private: int, board: int) -> Tuple[int, int]: return (private == board, private) # returns (pair?, high_rank)

    def _showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        pair0, high0 = self._rank_strength(gs["player_cards"][0], gs["board_card"])
        pair1, high1 = self._rank_strength(gs["player_cards"][1], gs["board_card"])
        if pair0 != pair1:      winner = 0 if pair0 else 1
        elif high0 != high1:    winner = 0 if high0 > high1 else 1
        else:                   return self._split_pot(reason="Exact tie.")
        return self._award(winner, reason=f"Showdown - Player {winner} wins. ")

    def _split_pot(self, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        split = gs["pot"] // 2
        gs["player_bank"][0] += split
        gs["player_bank"][1] += gs["pot"] - split
        gs["pot"] = 0
        self.broadcast(reason, ta.ObservationType.GAME_MESSAGE)
        return self._deal_new_hand()

    def _award(self, winner: int, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        gs["player_bank"][winner] += gs["pot"]
        gs["pot"] = 0
        reason += f"Current banks: Player 0: {gs['player_bank'][0]}; Player 1: {gs['player_bank'][1]}\n"
        self.broadcast(reason, ta.ObservationType.GAME_MESSAGE)
        return self._deal_new_hand()

    def _declare_match_winner(self, reason: str) -> ta.Outcome:
        b0, b1 = self.game_state["player_bank"].values()
        if b0 > b1:     return self.winner(0, reason + f" | stacks {b0}>{b1}")
        elif b1 > b0:   return self.winner(1, reason + f" | stacks {b1}>{b0}")
        else:           return self.draw(reason + " | equal stacks")
