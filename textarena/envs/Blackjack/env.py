import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta

class BlackjackEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    _ACTION_RE = re.compile(r"\[?\s*(hit|stand)\s*\]?", re.I)

    def __init__(self, num_hands: int):
        if not isinstance(num_hands, int) or isinstance(num_hands, bool) or num_hands < 1:
            raise ValueError("num_hands must be a positive integer")
        self.num_hands = num_hands
        self.ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
        self.suits = ['♠','♥','♦','♣']

    def setup(self) -> Dict[str, Any]:
        game_state = {"hand_number": 1, "num_hands": self.num_hands, "player_hand": [], "dealer_hand": [], "results_summary": {"win":0, "lose":0, "draw":0}}
        self._deal_initial_cards(game_state)  # deal first hand
        return game_state

    def on_start(self):
        self._observe_state()

    def _draw_card(self) -> str: return f"{self.rng.choice(self.ranks)}{self.rng.choice(self.suits)}" # infinite deck
    def _deal_initial_cards(self, game_state: Optional[Dict[str, Any]] = None):
        gs = game_state if game_state is not None else self.game_state
        gs["player_hand"] = [self._draw_card(), self._draw_card()]
        gs["dealer_hand"] = [self._draw_card(), self._draw_card()]

    def prompt(self, player_id: int) -> str:
        return (
            "You are playing Blackjack against the dealer.\nYour goal is to get as close to 21 as possible without going over.\n"
            "On your turn, reply 'hit' to draw another card or 'stand' to hold.\nJ/Q/K = 10 points; A = 11 or 1, whichever is better.\n"
        )

    def _hand_score(self, hand: List[str]) -> int:
        total, aces = 0, 0
        for card in hand:
            rank = card[:-1]
            if rank in ['J','Q','K']:   total += 10
            elif rank == 'A':           total += 11; aces += 1
            else:                       total += int(rank)
        while total > 21 and aces: # downgrade aces from 11 → 1 as needed
            total -= 10; aces -= 1
        return total

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self._ACTION_RE.fullmatch(move.strip())
        if m is None:
            return self.invalid("Invalid action. Use 'hit' or 'stand'.")
        if m.group(1).lower() == "hit":
            outcome = self._handle_hit()
        else:
            outcome = self._handle_stand()
        self._observe_state()  # only observe if valid
        return outcome

    def _handle_hit(self) -> Optional[ta.Outcome]:
        self.game_state["player_hand"].append(self._draw_card())
        if self._hand_score(self.game_state["player_hand"]) > 21: # player busts → record loss, then advance
            self.game_state["results_summary"]["lose"] += 1
            return self._advance_or_finish("bust")
        return None

    def _handle_stand(self) -> Optional[ta.Outcome]:
        while self._hand_score(self.game_state["dealer_hand"]) < 17: # dealer draws until ≥17
            self.game_state["dealer_hand"].append(self._draw_card())
        # compare scores
        p = self._hand_score(self.game_state["player_hand"])
        d = self._hand_score(self.game_state["dealer_hand"])
        if d > 21 or p > d:     self.game_state["results_summary"]["win"] += 1;   outcome = "win"
        elif p == d:            self.game_state["results_summary"]["draw"] += 1;  outcome = "draw"
        else:                   self.game_state["results_summary"]["lose"] += 1;  outcome = "lose"
        return self._advance_or_finish(outcome)

    def _advance_or_finish(self, outcome: str) -> Optional[ta.Outcome]:
        """After a hand ends, either start the next one or finish env."""
        message = (
            f"Hand {self.game_state['hand_number']}: you {outcome}. "
            f"Your final {self._hand_score(self.game_state['player_hand'])}, "
            f"Dealer {self._hand_score(self.game_state['dealer_hand'])} "
            f"({', '.join(self.game_state['dealer_hand'])})."
        )
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)
        if self.game_state["hand_number"] < self.game_state["num_hands"]: # prepare next hand
            self.game_state["hand_number"] += 1
            self.game_state["player_hand"].clear()
            self.game_state["dealer_hand"].clear()
            self._deal_initial_cards()
            return None
        else: # determine winner
            wins  = self.game_state["results_summary"]["win"]
            losses= self.game_state["results_summary"]["lose"]
            draws = self.game_state["results_summary"]["draw"]
            self.broadcast(f"=== All {self.game_state['num_hands']} hands complete ===\nWins: {wins}, Losses: {losses}, Draws: {draws}\n", ta.ObservationType.GAME_MESSAGE)
            return self.outcome({0: self._get_percentage_completion()}, reason=f"The game has concluded. Final scores: Dealer: {losses}, You: {wins}, Draws: {draws}")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _observe_state(self):
        gs = self.game_state
        score = self._hand_score(gs['player_hand'])
        msg = f"Hand {gs['hand_number']}/{gs['num_hands']}\nYour hand: {', '.join(gs['player_hand'])} (Score: {score})\nDealer shows: {gs['dealer_hand'][0]}"
        self.broadcast(msg, ta.ObservationType.GAME_MESSAGE)

    def _get_percentage_completion(self) -> float:
        """ Returns a reward based on win rate over total expected hands, preventing reward hacking by early exit. """
        gs = self.game_state
        if gs["num_hands"] == 0: return 0.0  # fallback safeguard
        return (gs["results_summary"]["win"] + 0.5 * gs["results_summary"]["draw"]) / gs["num_hands"]
