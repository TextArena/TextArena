import random, re
from typing import Dict, Any, Optional, Tuple

import textarena as ta
# from textarena.envs.GameOfPureStrategy.renderer import create_board_str  # TODO

class GameOfPureStrategyEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.full_hand = list(range(1, 14))
        self.action_space = re.compile(r"\[(a|k|q|j|10|[2-9])]", re.I)

    @staticmethod
    def _face_to_val(face: str) -> int:
        face = face.strip().lower()
        faces = {"a": 1, "j": 11, "q": 12, "k": 13}
        if face.isdigit(): return int(face)
        return faces.get(face)
    
    @staticmethod
    def _val_to_face(v: int) -> str: return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(v, str(v))
    # def get_board_str(self): return create_board_str(self.state.game_state) # TODO

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state={
            "round": 0, "prize_deck": random.sample(self.full_hand, k=13), "carry_pot": 0, "current_prize": None, 
            "player_hands": {0: self.full_hand.copy(), 1: self.full_hand.copy()}, "pending_bids": {}, "player_scores": {0: 0, 1: 0}, "starting_player": 0,
            }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._start_round()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def _start_round(self):
        gs = self.state.game_state
        gs["round"] += 1

        if gs["round"] > 13:
            s0, s1 = gs["player_scores"].values()
            if s0 > s1:     self.state.set_winner(0, self.m("outcome", "win_p0", s0=s0, s1=s1))
            elif s1 > s0:   self.state.set_winner(1, self.m("outcome", "win_p1", s0=s0, s1=s1))
            else:           self.state.set_draw(self.m("outcome", "draw", s=s0))
            return

        gs["current_prize"] = gs["prize_deck"][gs["round"] - 1]
        gs["pending_bids"] = {}
        gs["starting_player"] = 1 - gs["starting_player"]
        self.state.manually_set_current_player_id(gs["starting_player"])

        for pid in (0, 1):
            hand_str = " ".join(f"'[{self._val_to_face(c)}]'" for c in gs["player_hands"][pid])
            self.state.add_observation(to_id=pid, message=self.m("round", "header", round=gs['round'], prize=self._val_to_face(gs['current_prize']), worth=gs['current_prize'] + gs['carry_pot']), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.add_observation(to_id=pid, message=self.m("round", "hand", hand=hand_str), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        gs = self.state.game_state
        self.state.add_observation(from_id=pid, to_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        tokens = self.action_space.findall(action.lower())
        if len(tokens) != 1 or len(gs["pending_bids"]) >= 2:
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
            return self.state.step()

        face = tokens[0]
        bid_val = self._face_to_val(face)
        if bid_val not in gs["player_hands"][pid]:
            self.state.set_invalid_move(reason=self.m("invalid_move", "no_card"))
            return self.state.step()

        # record bid secretly
        gs["pending_bids"][pid] = bid_val
        gs["player_hands"][pid].remove(bid_val)

        # waiting for opponent?
        if len(gs["pending_bids"]) == 1: return self.state.step(rotate_player=True)

        bid0, bid1 = gs["pending_bids"][0], gs["pending_bids"][1]
        pot_value  = gs["current_prize"] + gs["carry_pot"]
        gs["carry_pot"] = 0

        if bid0 > bid1:     gs["player_scores"][0] += pot_value;    outcome = self.m("reveal", "p0_wins", pot=pot_value)
        elif bid1 > bid0:   gs["player_scores"][1] += pot_value;    outcome = self.m("reveal", "p1_wins", pot=pot_value)
        else:               gs["carry_pot"] += pot_value;           outcome = self.m("reveal", "tie", pot=gs['carry_pot'])
        self.state.add_observation(message=self.m("reveal", "bids", bid0=self._val_to_face(bid0), bid1=self._val_to_face(bid1), outcome=outcome), observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(message=self.m("reveal", "scores", s0=gs['player_scores'][0], s1=gs['player_scores'][1]), observation_type=ta.ObservationType.GAME_MESSAGE)

        self._start_round()
        return self.state.step(rotate_player=False)