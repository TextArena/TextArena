import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.LiarsDice.renderer import create_board_str


class LiarsDiceEnv(ta.GameEnv):
    min_players = 2
    max_players = 15
    mdp_includes_actions = False

    # Matched against the stripped action; no two adjacent whitespace quantifiers,
    # so padded input cannot trigger quadratic backtracking.
    _CALL_RE = re.compile(r"call", re.IGNORECASE)
    _BID_RE = re.compile(r"bid\s*(?::\s*)?(\d+)[,\s]+(\d+)", re.IGNORECASE)

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
            f"You are Player {player_id} in a {self.state.num_players}-player game of Liar's Dice.\n"
            f"Every player starts with {self.num_dice} six-sided dice. At the start of each round all dice are re-rolled; "
            "you only see your own dice, and the board shows how many dice everyone has left.\n"
            "On your turn, reply with exactly one of:\n"
            "  - 'Bid: <quantity>, <face>' (e.g. 'Bid: 3, 4') to claim that at least <quantity> of all dice in play "
            "show <face>. Faces are 1-6 and nothing is wild. A new bid must either raise the quantity (with any face) "
            "or keep the quantity and raise the face. The quantity cannot exceed the number of dice in play.\n"
            "  - 'Call' to challenge the current bid. All dice are revealed: if fewer dice show that face than the bid "
            "claims, the bidder loses one die; otherwise you, the caller, lose one die.\n"
            "The loser of a challenge starts the next round. A player with no dice left is out, and the last player "
            "with dice wins."
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        command = action.strip()
        if self._CALL_RE.fullmatch(command):
            current_bid, last_bidder_id = gs["current_bid"], gs["last_bidder_id"]
            if last_bidder_id is None or current_bid["quantity"] == 0:
                return self.invalid("Call made with no prior bid.")
            if last_bidder_id == player_id:
                return self.invalid("You cannot call your own bid.")
            face, quantity = current_bid["face_value"], current_bid["quantity"]
            total_face_count = sum(dice.count(face) for dice in gs["dice_rolls"].values())
            revealed = "; ".join(
                f"Player {pid}: {', '.join(map(str, dice))}" for pid, dice in sorted(gs["dice_rolls"].items())
            )
            msg = f"Player {player_id} calls! Revealed dice - {revealed}.\n"
            if total_face_count < quantity:  # last bidder was bluffing
                loser_id = last_bidder_id
                msg += f"The actual count of face {face} is {total_face_count}, which is LESS than {quantity}.\nPlayer {loser_id} (the last bidder) loses one die."
            else:
                loser_id = player_id
                msg += f"The actual count of face {face} is {total_face_count}, which is >= {quantity}.\nPlayer {loser_id} (the caller) loses one die."
            return self._apply_die_loss(loser_id, msg)

        bid_match = self._BID_RE.fullmatch(command)
        if bid_match:
            quantity_text, face_text = bid_match.groups()
            new_quantity = int(quantity_text) if len(quantity_text) <= 9 else None
            new_face_value = int(face_text) if len(face_text) <= 2 else None
            is_valid, reason = self._is_valid_bid(new_quantity, new_face_value, gs["current_bid"])
            if not is_valid:
                return self.invalid(f"Invalid bid: {reason}")
            gs["current_bid"] = {"quantity": new_quantity, "face_value": new_face_value}
            gs["last_bidder_id"] = player_id
            self.broadcast(f"Player {player_id} bids {new_quantity} of face {new_face_value}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return None

        return self.invalid("Action not recognized. Reply with either 'Bid: <quantity>, <face>' (e.g. 'Bid: 3, 4') or 'Call'.")

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

    def _total_dice(self) -> int:
        return sum(self.game_state["remaining_dice"].values())

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

    def _is_valid_bid(self, new_quantity: Optional[int], new_face_value: Optional[int], current_bid: Dict[str, int]) -> Tuple[bool, str]:
        total_dice = self._total_dice()
        if new_quantity is not None and new_quantity < 1: return False, "Quantity must be at least 1."
        if new_quantity is None or new_quantity > total_dice:
            return False, f"Quantity cannot exceed the {total_dice} dice in play."
        if new_face_value is None or not (1 <= new_face_value <= 6): return False, "Face value must be between 1 and 6."
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
