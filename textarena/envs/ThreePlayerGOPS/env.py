import random, re
from typing import Dict, Any, Optional, Tuple, List

import textarena as ta


class ThreePlayerGOPSEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.full_hand: List[int] = list(range(1, 14))
        self.action_space = re.compile(r"\[(a|k|q|j|10|[2-9])\]", re.I)

    @staticmethod
    def _face_to_val(face: str) -> int:
        face = face.strip().lower().strip("[]")   # ← remove stray brackets
        faces = {"a": 1, "j": 11, "q": 12, "k": 13}
        return int(face) if face.isdigit() else faces[face]

    @staticmethod
    def _val_to_face(v: int) -> str:
        return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(v, str(v))

    def _handle_invalid(self, reason: str) -> Tuple[bool, Dict[str, Any]]:
        eliminated_now = self.state.set_invalid_move(reason)
        if not eliminated_now: return self.state.step(rotate_player=False) # warning only – let the same player retry (no rotation)
        # player eliminated
        pid = self.state.current_player_id
        self.state.add_observation(message=self.m("elimination", "player", pid=pid), observation_type=ta.ObservationType.GAME_MESSAGE,)
        alive = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        if len(alive) == 1:                      # instant win
            winner = alive[0]
            rewards = {p: (+1 if p == winner else -1) for p in range(self.state.num_players)}
            self.state.set_game_outcome(reward_dict=rewards, reason=self.m("outcome", "auto_win"))
            return True, self.state.step_info

        # hand control to next alive player
        self.state.current_player_id = self.state.next_alive_player() or alive[0]
        return self.state.step(rotate_player=False)

    def reset(self, num_players: int, seed: Optional[int] = None):
        assert num_players == 3, f"Three-player GOPS requires exactly 3 players (got {num_players})."
        self.state = ta.FFAMultiPlayerState(num_players=num_players, seed=seed)

        game_state = {
            "round": 0,
            "prize_deck": random.sample(self.full_hand, k=13),
            "carry_pot": 0,
            "current_prize": None,
            "player_hands": {pid: self.full_hand.copy() for pid in range(3)},
            "pending_bids": {},
            "player_scores": {pid: 0 for pid in range(3)},
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._start_round()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def _start_round(self):
        gs = self.state.game_state
        gs["round"] += 1
        if gs["round"] > 13: # end-of-game (after 13 prize cards)
            scores = gs["player_scores"]
            ranked = sorted(scores, key=lambda p: (-scores[p], p))
            uniq = sorted({v for v in scores.values()}, reverse=True)
            if len(uniq) == 1: rewards = {p: 0 for p in scores} # triple tie
            elif len(uniq) == 2: # a tie pair
                top, low = uniq
                top_tied = [p for p, s in scores.items() if s == top]
                low_tied = [p for p, s in scores.items() if s == low]
                if len(top_tied) == 2:  rewards = {p: (+1 if p in top_tied else -1) for p in scores} # tie for first
                else:                   rewards = {p: (-1 if p in low_tied else +1) for p in scores} # tie for last
            else: rewards = {ranked[0]: +1, ranked[1]: 0, ranked[2]: -1} # distinct scores
            self.state.set_game_outcome(reward_dict=rewards, reason=self.m("outcome", "final", scores=scores))
            return

        gs["current_prize"] = gs["prize_deck"][gs["round"] - 1]
        gs["pending_bids"] = {}

        for pid in range(3):
            hand_str = " ".join(f"'[{self._val_to_face(c)}]'" for c in gs["player_hands"][pid])
            self.state.add_observation(to_id=pid, message=self.m("round", "header", round=gs['round'], prize=self._val_to_face(gs['current_prize']), worth=gs['current_prize'] + gs['carry_pot']), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.add_observation(to_id=pid, message=self.m("round", "hand", hand=hand_str), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        gs = self.state.game_state
        self.state.add_observation(from_id=pid, to_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) # record player action for themselves
        tokens = self.action_space.findall(action.lower())
        if not tokens: return self._handle_invalid(self.m("invalid_move", "no_token")) # no valid token at all
        bid_val = self._face_to_val(tokens[-1])              # <- take the final match
        if bid_val not in gs["player_hands"][pid]:
            return self._handle_invalid(self.m("invalid_move", "bad_card"))
        
        gs["pending_bids"][pid] = bid_val
        gs["player_hands"][pid].remove(bid_val)
        alive_players = [p for p in range(self.state.num_players) if self.state.is_player_alive(p)]
        if len(gs["pending_bids"]) < len(alive_players):
            return self.state.step()   # rotate to next player
        bids = gs["pending_bids"]
        pot = gs["current_prize"] + gs["carry_pot"]
        gs["carry_pot"] = 0

        max_bid = max(bids.values())
        winners = [p for p, v in bids.items() if v == max_bid]

        bids_str = ", ".join(f"P{p}:{self._val_to_face(v)}" for p, v in bids.items())
        if len(winners) == 1:
            winner = winners[0]
            gs["player_scores"][winner] += pot
            reveal = self.m("reveal", "win", bids=bids_str, winner=winner, pot=pot)
        else:
            gs["carry_pot"] = pot
            reveal = self.m("reveal", "tie", bids=bids_str, pot=gs['carry_pot'])

        self.state.add_observation(message=reveal, observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(message=self.m("reveal", "scores", scoreline="  ".join(f"P{p}:{s}" for p, s in gs["player_scores"].items())), observation_type=ta.ObservationType.GAME_MESSAGE)

        self._start_round()
        return self.state.step()
