import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.LiarsDice.renderer import create_board_str


class LiarsDiceEnv(ta.GameEnv):
    min_players = 2
    max_players = 15

    def __init__(self, num_dice: int = 5):
        """
        Args:
            num_dice (int): Initial number of dice each player starts with.
        """
        if not isinstance(num_dice, int) or isinstance(num_dice, bool) or num_dice < 1:
            raise ValueError("num_dice must be a positive integer")
        self.num_dice = num_dice

    def setup(self) -> Dict[str, Any]:
        return {
            "current_bid": {"quantity": 0, "face_value": 0},
            "last_bidder_id": None,
            "remaining_dice": {pid: self.num_dice for pid in range(self.state.num_players)},
            "dice_rolls": None,
        }

    def on_start(self):
        self._roll_new_dice()

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in an {self.state.num_players}-player Liar's Dice game.\n"
            "Rules:\n- On your turn, you may either:\n  1) Make a new bid with a higher quantity or higher face (or both) than the current bid; i.e. 'Bid: 3, 4',\n  2) Call the last bid by replying 'Call'.\n\n"
            "If you call:\n  - If the actual count of that face value among all dice is less than the bid, the last bidder loses one die.\n"
            "  - Otherwise, the caller loses one die.\nA player who reaches 0 dice is eliminated. The last remaining player wins."
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if re.match(r"^\s*\[?\s*call\s*\]?\s*$", action, re.IGNORECASE):
            current_bid, last_bidder_id = gs["current_bid"], gs["last_bidder_id"]
            if last_bidder_id is None or current_bid["quantity"] == 0:
                return self.invalid("Call made with no prior bid.")
            if last_bidder_id == player_id:
                return self.invalid("You cannot call your own bid.")
            total_face_count = sum(dice.count(current_bid["face_value"]) for dice in gs["dice_rolls"].values())
            if total_face_count < current_bid["quantity"]:  # last bidder was bluffing
                loser_id = last_bidder_id
                msg = f"Player {player_id} calls! The actual count of face {current_bid['face_value']} is {total_face_count}, which is LESS than {current_bid['quantity']}.\nPlayer {loser_id} (the last bidder) loses one die."
            else:
                loser_id = player_id
                msg = f"Player {player_id} calls! The actual count of face {current_bid['face_value']} is {total_face_count}, which is >= {current_bid['quantity']}.\nPlayer {loser_id} (the caller) loses one die."
            return self._apply_die_loss(loser_id, msg)

        bid_match = re.match(r"^\s*\[?\s*bid\s*:?\s*(\d+)[,\s]+(\d+)\s*\]?\s*$", action, re.IGNORECASE)
        if bid_match:
            try:
                new_quantity = int(bid_match.group(1))
                new_face_value = int(bid_match.group(2))
            except ValueError:
                return self.invalid("Invalid bid: quantity and face value are too large.")
            is_valid, reason = self._is_valid_bid(new_quantity, new_face_value, gs["current_bid"])
            if not is_valid:
                return self.invalid(f"Invalid bid: {reason}")
            gs["current_bid"] = {"quantity": new_quantity, "face_value": new_face_value}
            gs["last_bidder_id"] = player_id
            self.broadcast(f"Player {player_id} bids {new_quantity} of face {new_face_value}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return None

        return self.invalid(f"Action not recognized as either a valid 'Bid: X, Y' or 'Call'. Submitted action: {action}")

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        self.eliminate(player_id)
        self.broadcast(f"Player {player_id} was eliminated by invalid move.", ta.ObservationType.GAME_MESSAGE)
        self.game_state["remaining_dice"][player_id] = 0
        if len(self.state.alive_players) <= 1:
            return self._final_outcome()
        self._roll_new_dice()
        return None

    def get_board_str(self):
        return create_board_str(
            game_state=self.state.game_state,
            player_id=self.state.current_player_id,
        )

    def render(self, player_id: int) -> str:
        return create_board_str(game_state=self.state.game_state, player_id=player_id)

    def _roll_new_dice(self):
        gs = self.game_state
        gs["current_bid"] = {"quantity": 0, "face_value": 0}
        gs["last_bidder_id"] = None
        gs["dice_rolls"] = {
            pid: [self.rng.randint(1, 6) for _ in range(count)]
            for pid, count in gs["remaining_dice"].items()
            if self.state.is_player_alive(pid)
        }
        for pid, rolled in gs["dice_rolls"].items():  # send each player their new private dice
            message = "\nNew round - Remaining dice: " + "; ".join([f"\tPlayer {p}: {d}" for p, d in gs["remaining_dice"].items()]) + f"\nYour current Dice are: {', '.join(map(str, rolled))}"
            self.message(pid, message, ta.ObservationType.GAME_BOARD)

    def _apply_die_loss(self, loser_id: int, message: str) -> Optional[ta.Outcome]:
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)
        self.game_state["remaining_dice"][loser_id] -= 1
        if self.game_state["remaining_dice"][loser_id] == 0:
            self.eliminate(loser_id)
        if len(self.state.alive_players) <= 1:
            return self._final_outcome()
        self._roll_new_dice()
        if self.state.is_player_alive(loser_id):
            self.set_next_player(loser_id)
        else:
            for offset in range(1, self.state.num_players + 1):
                candidate = (loser_id + offset) % self.state.num_players
                if self.state.is_player_alive(candidate):
                    self.set_next_player(candidate)
                    break
        return None

    def _is_valid_bid(self, new_quantity: int, new_face_value: int, current_bid: Dict[str, int]) -> Tuple[bool, str]:
        if new_quantity < 1: return False, "Quantity must be at least 1."
        if not (1 <= new_face_value <= 6): return False, "Face value must be between 1 and 6."
        if new_quantity < current_bid['quantity']:
            return False, f"New quantity {new_quantity} is lower than current {current_bid['quantity']}."
        if (
            new_quantity == current_bid['quantity']
            and new_face_value <= current_bid['face_value']
        ):
            return False, "At the same quantity, the face value must increase."
        return True, ""

    def _final_outcome(self) -> ta.Outcome:
        """Rank-scaled rewards: first eliminated gets -1, winner gets +1."""
        final_ranking = self.state.eliminated + self.state.alive_players
        rewards = {pid: -1.0 + 2.0 * (rank / (self.state.num_players - 1)) for rank, pid in enumerate(final_ranking)}
        return self.outcome(rewards, reason=f"Player {final_ranking[-1]} wins! Final ranking: {final_ranking}")
