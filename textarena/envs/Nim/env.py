import re
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta
from textarena.envs.Nim.renderer import create_board_str

class NimEnv(ta.Env):
    def __init__(self, piles: List[int] = None):
        """
        Args:
            piles (List[int]): Initial sizes of the piles (e.g. [3, 5, 7]). If None, defaults to [3,4,5].
        """
        super().__init__()
        self.initial_piles = piles if piles is not None else [3, 4, 5]

    def get_board_str(self):
        return create_board_str(self.state.game_state["piles"])

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"piles": self.initial_piles.copy()}, player_prompt_function=self._prompt)
        self.state.add_observation(message=self.m("state", "current_pile", pile_0=self.state.game_state["piles"][0], pile_1=self.state.game_state["piles"][1], pile_2=self.state.game_state["piles"][2]), observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._execute_move(action) # Execute the move (or mark invalid if the format is incorrect/illegal)
        self.state.add_observation(message=self.m("state", "current_pile", pile_0=self.state.game_state["piles"][0], pile_1=self.state.game_state["piles"][1], pile_2=self.state.game_state["piles"][2]), observation_type=ta.ObservationType.GAME_BOARD) # After the current player moves, send the updated board to the opponent.
        self._check_game_over() # Check if the game is over
        return self.state.step() # Proceed to the next turn (or finalize if done)

    def _execute_move(self, action: str) -> None:
        match = re.compile(r"\[\s*(\d+)\s+(\d+)\s*\]").search(action.strip()) # We'll look for actions in the format [pile_index quantity_to_remove], e.g. [1 3].
        if not match: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format")); return
        try: pile_index, quantity = map(int, match.groups()) # Extract pile index and quantity to remove
        except ValueError: self.state.set_invalid_move(reason=self.m("invalid_move", "correct_format_wrong_fields")); return
        # Validate the move
        if not (0 <= pile_index < len(self.state.game_state["piles"])): self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_range", pile_index=pile_index)); return
        if quantity <= 0: self.state.set_invalid_move(reason=self.m("invalid_move", "non_positive")); return
        if self.state.game_state["piles"][pile_index] < quantity: self.state.set_invalid_move(reason=self.m("invalid_move", "exceeds_pile", quantity=quantity, pile_index=pile_index, pile_count=self.state.game_state['piles'][pile_index])); return
        self.state.game_state["piles"][pile_index] -= quantity # Perform the removal
        self.state.add_observation(message=self.m("observation", "removed_from_piles", player_id=self.state.current_player_id, quantity=quantity, pile_index=pile_index), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION) # Announce the move

    def _check_game_over(self) -> None:
        if all(pile == 0 for pile in self.state.game_state["piles"]):
            self.state.set_winner(player_id=self.state.current_player_id, reason=self.t("outcome", "win", player_id=self.state.current_player_id))

    def _render_piles(self) -> str:
        lines = []
        for i, amt in enumerate(self.state.game_state["piles"]):
            lines.append(f"  {self.t('state', 'pile')} {i}: {amt}")
        return "\n".join(lines)