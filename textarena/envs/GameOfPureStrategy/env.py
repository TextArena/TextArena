import re
from typing import Any, Dict, Optional, Union

import textarena as ta
# from textarena.envs.GameOfPureStrategy.renderer import create_board_str  # TODO

class GameOfPureStrategyEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    broadcast_actions = False  # bids are secret: raw actions echoed only to their author

    def __init__(self):
        self.full_hand = list(range(1, 14))
        self.action_space = re.compile(
            r"^\s*(?P<legacy>\[)?\s*(?P<card>a|k|q|j|10|[2-9])\s*(?(legacy)\])\s*$",
            re.IGNORECASE,
        )

    @staticmethod
    def _face_to_val(face: str) -> int:
        face = face.strip().lower()
        faces = {"a": 1, "j": 11, "q": 12, "k": 13}
        if face.isdigit(): return int(face)
        return faces.get(face)

    @staticmethod
    def _val_to_face(v: int) -> str: return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(v, str(v))
    # def get_board_str(self): return create_board_str(self.game_state) # TODO

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 0, "prize_deck": self.rng.sample(self.full_hand, k=13), "carry_pot": 0, "current_prize": None,
            "player_hands": {0: self.full_hand.copy(), 1: self.full_hand.copy()}, "pending_bids": {}, "player_scores": {0: 0, 1: 0}, "starting_player": 0,
        }

    def on_start(self):
        self._start_round()  # cannot end the game here (round becomes 1)
        self.set_current_player(self.game_state["starting_player"])

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a match of GameOfPureStrategy.\n- You hold the 13 cards A-K; each can be used once.\n- Each round a prize card is revealed. Play exactly ONE card "
            f"by replying with its face, such as 'Q', '10', or '2'.\n- Higher card wins the prize (plus carry-over). Ties roll prize "
            f"into the pot for next round.\n- Highest total after 13 rounds wins."
        )

    def render(self, player_id: int) -> str:
        """Show public scores and only the viewer's private hand/bid status."""
        gs = self.game_state
        hand = " ".join(self._val_to_face(card) for card in gs["player_hands"][player_id])
        bid_status = "submitted" if player_id in gs["pending_bids"] else "not submitted"
        return (
            f"Round {gs['round']}/13 | Prize: {self._val_to_face(gs['current_prize'])} "
            f"| Carry: {gs['carry_pot']}\n"
            f"Scores: P0 {gs['player_scores'][0]} | P1 {gs['player_scores'][1]}\n"
            f"Your remaining hand: {hand}\nYour bid is {bid_status}."
        )

    def _start_round(self) -> Optional[ta.Outcome]:
        gs = self.game_state

        if gs["round"] >= 13:
            s0, s1 = gs["player_scores"].values()
            if s0 > s1:     return self.winner(0, f"P0 {s0} vs P1 {s1}")
            elif s1 > s0:   return self.winner(1, f"P1 {s1} vs P0 {s0}")
            else:           return self.draw(f"Both scored {s0}")
        gs["round"] += 1

        gs["current_prize"] = gs["prize_deck"][gs["round"] - 1]
        gs["pending_bids"] = {}
        gs["starting_player"] = 1 - gs["starting_player"]

        for pid in (0, 1):
            hand_str = " ".join(self._val_to_face(c) for c in gs["player_hands"][pid])
            self.message(pid, f"### Round {gs['round']}/13 - Prize: {self._val_to_face(gs['current_prize'])}  (worth {gs['current_prize'] + gs['carry_pot']})", ta.ObservationType.GAME_MESSAGE)
            self.message(pid, f"Your remaining hand: {hand_str}", ta.ObservationType.GAME_BOARD)
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state

        match = self.action_space.fullmatch(action)
        if match is None or len(gs["pending_bids"]) >= 2:
            return self.invalid("Submit exactly one card face.")

        bid_val = self._face_to_val(match.group("card"))
        if player_id in gs["pending_bids"]:
            return self.invalid("You already submitted a bid this round.")
        if bid_val not in gs["player_hands"][player_id]:
            return self.invalid("You no longer have that card.")

        # record bid secretly
        gs["pending_bids"][player_id] = bid_val
        gs["player_hands"][player_id].remove(bid_val)

        # waiting for opponent?
        if len(gs["pending_bids"]) == 1: return None  # default rotation

        bid0, bid1 = gs["pending_bids"][0], gs["pending_bids"][1]
        pot_value  = gs["current_prize"] + gs["carry_pot"]
        gs["carry_pot"] = 0

        reveal = (f"Bids: P0 {self._val_to_face(bid0)} vs P1 {self._val_to_face(bid1)} - ")
        if bid0 > bid1:     gs["player_scores"][0] += pot_value;    reveal += f"Player 0 wins {pot_value}."
        elif bid1 > bid0:   gs["player_scores"][1] += pot_value;    reveal += f"Player 1 wins {pot_value}."
        else:               gs["carry_pot"] += pot_value;           reveal += f"Tie -> pot now {gs['carry_pot']}."
        self.broadcast(reveal, ta.ObservationType.GAME_MESSAGE)
        self.broadcast(f"Scores -> P0:{gs['player_scores'][0]}  P1:{gs['player_scores'][1]}", ta.ObservationType.GAME_MESSAGE)

        outcome = self._start_round()
        if outcome is not None: return outcome
        self.set_next_player(gs["starting_player"])
        return None
