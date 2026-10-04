import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class LeducHoldemEnv(ta.GameEnv):
    """
    Two-player Leduc Hold’em (6-card deck: JJQQKK in 2 suits).
    • Ante 1 chip -> each gets 1 private card.
    • Pre-flop betting (check/bet/raise/call/fold; fixed bet = 2 chips, at most two bets per round:
      the opening bet and one raise).
    • Reveal one public card -> second betting round (bet = 4 chips).
    • Showdown: pair > high card; ties split pot.
    """
    min_players = 2
    max_players = 2
    max_bets_per_round = 2  # the opening bet plus one raise, as in the standard game

    def __init__(self, starting_bank: int = 100, max_rounds: int = 5):
        if not isinstance(starting_bank, int) or isinstance(starting_bank, bool) or starting_bank < 1:
            raise ValueError("starting_bank must be a positive integer")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer")
        self.starting_bank = starting_bank
        self.deck = [r for r in range(3) for _ in range(2)] # deck = two of each rank 0-2  (0=J, 1=Q, 2=K)
        self.bet_sizes = [2, 4] # round-0 / round-1 fixed bet
        self.max_rounds = max_rounds
        self.action_space = re.compile(r"^(check|call|bet|raise|fold)$", re.I)

    @staticmethod
    def _rank_to_str(r: int) -> str: return ["J", "Q", "K"][r]

    def _legal(self, gs, pid) -> List[str]: # ordered so every message lists actions identically
        bet_unit = self.bet_sizes[gs["round"]]
        if gs["current_bet"] == 0:
            legal = ["check"]
            if self._can_reach_target(gs, pid, bet_unit):
                legal.append("bet")
            return legal

        legal = []
        to_call = gs["current_bet"] - gs["round_bets"][pid]
        if to_call <= gs["player_bank"][pid]:
            legal.append("call")
        next_target = gs["current_bet"] + bet_unit
        if 1 + gs["raises_this_round"] < self.max_bets_per_round and self._can_reach_target(gs, pid, next_target):
            legal.append("raise")
        legal.append("fold")
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
            f"Fixed bet sizes: 2 chips pre-flop, 4 chips post-flop (at most two bets per round: the opening bet and one raise).\n"
            f"Rules:\n"
            f"- The deck has six cards: two Jacks, two Queens and two Kings (J < Q < K).\n"
            f"- Every hand, both players ante 1 chip and get one private card. After the first betting round one public card is revealed, followed by a second betting round.\n"
            f"- At showdown, a private card that pairs the public card wins; otherwise the higher private card wins. Equal cards split the pot.\n"
            f"- The match lasts {self.max_rounds} hands (or until a player cannot pay the ante). Both players start with {self.starting_bank} chips; whoever has more chips at the end wins."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        opponent = 1 - player_id
        board = self._rank_to_str(gs["board_card"]) if gs["board_revealed"] else "not revealed yet"
        to_call = gs["current_bet"] - gs["round_bets"][player_id]
        lines = [
            f"Hand {gs['hands_dealt']} of {self.max_rounds} - {'pre-flop' if gs['round'] == 0 else 'post-flop'} betting",
            f"Your card: {self._rank_to_str(gs['player_cards'][player_id])} | Public card: {board}",
            f"Pot: {gs['pot']} | Your chips: {gs['player_bank'][player_id]} | Opponent chips: {gs['player_bank'][opponent]}",
            f"Bet this round: {gs['current_bet']} (to call: {to_call}); bets made this round: "
            f"{(1 + gs['raises_this_round']) if gs['current_bet'] else 0} of {self.max_bets_per_round}",
        ]
        if not self.state.done:
            lines.append("Valid actions: " + ", ".join(f"'{a}'" for a in self._legal(gs, player_id)))
        return "\n".join(lines)

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
            return self.invalid("Illegal now. Allowed: " + ", ".join(f"'{a}'" for a in legal) + ".")

        bet_unit = self.bet_sizes[gs["round"]]

        if move == "check":
            self.broadcast(f"Player {pid} checks.", ta.ObservationType.GAME_MESSAGE)
            if gs.get("prev_check"):
                return self._finish_betting_round()
            gs["prev_check"] = True
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

        return None  # betting continues with the other player

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

    def _next_round_or_showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if gs["round"] == 0:                   # flop round begins
            gs.update({"round": 1, "current_bet": 0, "round_bets": {0: 0, 1: 0}, "raises_this_round": 0, "prev_check": False, "board_revealed": True})
            card = self._rank_to_str(gs["board_card"])
            self.broadcast(f"Flop card revealed: {card}", ta.ObservationType.GAME_MESSAGE)
            return None
        else:
            return self._showdown()

    def _rank_strength(self, private: int, board: int) -> Tuple[int, int]: return (private == board, private) # returns (pair?, high_rank)

    def _showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        cards = gs["player_cards"]
        reveal = (
            f"Showdown: Player 0 shows {self._rank_to_str(cards[0])}, Player 1 shows {self._rank_to_str(cards[1])}; "
            f"the public card is {self._rank_to_str(gs['board_card'])}."
        )
        pair0, high0 = self._rank_strength(cards[0], gs["board_card"])
        pair1, high1 = self._rank_strength(cards[1], gs["board_card"])
        if pair0 != pair1:      winner = 0 if pair0 else 1
        elif high0 != high1:    winner = 0 if high0 > high1 else 1
        else:                   return self._split_pot(reason=f"{reveal} Exact tie: the pot of {gs['pot']} is split.")
        return self._award(winner, reason=f"{reveal} Player {winner} wins the pot of {gs['pot']}.")

    def _split_pot(self, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        split = gs["pot"] // 2
        gs["player_bank"][0] += split
        gs["player_bank"][1] += gs["pot"] - split
        gs["pot"] = 0
        self.broadcast(f"{reason} Current banks: Player 0: {gs['player_bank'][0]}; Player 1: {gs['player_bank'][1]}", ta.ObservationType.GAME_MESSAGE)
        return self._deal_new_hand()

    def _award(self, winner: int, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        gs["player_bank"][winner] += gs["pot"]
        gs["pot"] = 0
        reason += f" Current banks: Player 0: {gs['player_bank'][0]}; Player 1: {gs['player_bank'][1]}"
        self.broadcast(reason, ta.ObservationType.GAME_MESSAGE)
        return self._deal_new_hand()

    def _declare_match_winner(self, reason: str) -> ta.Outcome:
        b0, b1 = self.game_state["player_bank"].values()
        if b0 > b1:     return self.winner(0, reason + f" | stacks {b0}>{b1}")
        elif b1 > b0:   return self.winner(1, reason + f" | stacks {b1}>{b0}")
        else:           return self.draw(reason + " | equal stacks")
