import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta


class ThreePlayerGOPSEnv(ta.GameEnv):
    min_players = 3
    max_players = 3
    broadcast_actions = False  # sealed bids: raw actions echoed only to their author

    def __init__(self):
        self.full_hand: List[int] = list(range(1, 14))
        # A whitespace run must be consumable by only one \s*, as retrying every split of a long run is quadratic.
        self.action_space = re.compile(r"^\s*(?:\[\s*)?(a|k|q|j|10|[2-9])(?:\s*\])?\s*$", re.I)

    @staticmethod
    def _face_to_val(face: str) -> int:
        face = face.strip().lower().strip("[]")
        faces = {"a": 1, "j": 11, "q": 12, "k": 13}
        return int(face) if face.isdigit() else faces[face]

    @staticmethod
    def _val_to_face(v: int) -> str:
        return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(v, str(v))

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 0,
            "prize_deck": self.rng.sample(self.full_hand, k=13),
            "carry_pot": 0,
            "current_prize": None,
            "player_hands": {pid: self.full_hand.copy() for pid in range(3)},
            "pending_bids": {},
            "player_scores": {pid: 0 for pid in range(3)},
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Three-Player GOPS.\n"
            "- You hold the 13 cards A-K (each exactly once).\n"
            "- Each round a prize is revealed. Reply with ONE card like `Q`, "
            "`10`, `2` …\n"
            "- Highest card wins the prize (+ any carry-over pot). "
            "Ties roll the prize into the next round.\n"
            "- After 13 rounds, rewards follow the ranking by total: highest +1, lowest -1, middle 0. "
            "Two players tied ahead of the third both get +1, two tied behind both get -1, and a three-way tie gives everyone 0.\n"
            "- Two invalid moves in a row eliminate you with -1; the others play on and are ranked among themselves, and a lone survivor wins."
        )

    def on_start(self):
        self._start_round()

    def _start_round(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        gs["round"] += 1
        if gs["round"] > 13: # end-of-game (after 13 prize cards)
            return self._final_outcome()

        gs["current_prize"] = gs["prize_deck"][gs["round"] - 1]
        gs["pending_bids"] = {}

        for pid in range(3):
            hand_str = " ".join(f"'{self._val_to_face(c)}'" for c in gs["player_hands"][pid])
            self.message(pid, f"### Round {gs['round']}/13 - Prize: {self._val_to_face(gs['current_prize'])} (worth {gs['current_prize'] + gs['carry_pot']})", ta.ObservationType.GAME_MESSAGE)
            self.message(pid, f"Your remaining hand: {hand_str}", ta.ObservationType.GAME_BOARD)
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        card_match = self.action_space.match(action)
        if not card_match:
            return self.invalid("action must be a single card like 'Q', '10' or '2'")
        bid_val = self._face_to_val(card_match.group(1))
        if bid_val not in gs["player_hands"][player_id]:
            return self.invalid("card already used or invalid")

        gs["pending_bids"][player_id] = bid_val
        gs["player_hands"][player_id].remove(bid_val)
        return self._resolve_bids_if_ready()

    def _resolve_bids_if_ready(self) -> Optional[ta.Outcome]:
        """Resolve once every surviving player has a bid in the sealed round."""
        gs = self.game_state
        alive = self.state.alive_players
        if not all(pid in gs["pending_bids"] for pid in alive):
            return None  # rotate to next player

        bids = {pid: gs["pending_bids"][pid] for pid in alive}
        pot = gs["current_prize"] + gs["carry_pot"]
        gs["carry_pot"] = 0

        max_bid = max(bids.values())
        winners = [p for p, v in bids.items() if v == max_bid]

        if len(winners) == 1:
            winner = winners[0]
            gs["player_scores"][winner] += pot
            reveal = (f"Bids » " + ", ".join(f"P{p}:{self._val_to_face(v)}" for p, v in bids.items()) + f" - Player {winner} wins {pot}.")
        else:
            gs["carry_pot"] = pot
            reveal = (f"Bids » " + ", ".join(f"P{p}:{self._val_to_face(v)}" for p, v in bids.items()) + f" - tie, pot now {gs['carry_pot']}.")

        self.broadcast(reveal, ta.ObservationType.GAME_MESSAGE)
        self.broadcast("Scores → " + "  ".join(f"P{p}:{s}" for p, s in gs["player_scores"].items()), ta.ObservationType.GAME_MESSAGE)
        return self._start_round()

    def _final_outcome(self) -> ta.Outcome:
        """Rank surviving players by score while keeping eliminations punitive."""
        scores = self.game_state["player_scores"]
        alive = self.state.alive_players
        score_groups: List[List[int]] = []
        for pid in sorted(alive, key=lambda p: (scores[p], p)):
            if not score_groups or scores[pid] != scores[score_groups[-1][0]]:
                score_groups.append([pid])
            else:
                score_groups[-1].append(pid)

        rewards: Dict[int, float] = {pid: -1 for pid in self.state.eliminated}
        if len(score_groups) == 1:
            # A genuine score draw is neutral. A sole survivor has already won
            # through elimination and is rewarded accordingly.
            reward = 1 if len(alive) == 1 and self.state.eliminated else 0
            rewards.update({pid: reward for pid in score_groups[0]})
        else:
            for idx, group in enumerate(score_groups):
                reward = -1.0 + 2.0 * idx / (len(score_groups) - 1)
                rewards.update({pid: reward for pid in group})
        return self.outcome(rewards, reason=f"Final scores: {scores}")

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        self.eliminate(player_id)
        self.game_state["pending_bids"].pop(player_id, None)
        self.broadcast(f"Player {player_id} eliminated after repeated invalid moves.", ta.ObservationType.GAME_MESSAGE)
        alive = self.state.alive_players
        if len(alive) == 1:  # instant win
            winner = alive[0]
            rewards = {p: (+1 if p == winner else -1) for p in range(self.state.num_players)}
            return self.outcome(rewards, reason="Two players eliminated - automatic win.")
        # If the eliminated player was the final bidder in the turn order, the
        # surviving players have already submitted. Resolve now rather than
        # rotating back and allowing one of them to overwrite a sealed bid.
        if all(pid in self.game_state["pending_bids"] for pid in alive):
            return self._resolve_bids_if_ready()
        return None
