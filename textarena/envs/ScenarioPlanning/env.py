import os, json, random, importlib
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.ScenarioPlanning.renderer import create_board_str

class ScenarioPlanningEnv(ta.Env):
    def __init__(self, jury_class: Optional[Any] = None, jury_size: Optional[int] = 5, scenarios_path: Optional[str] = None,):
        """
        Args:
            num_judges (int): Number of judges evaluating the strategies.
            judge_class (ta.JudgeVote): The judge evaluation class.
            scenarios_path (str): Path to the JSON file containing scenarios.
        """
        if jury_class is None:
            from textarena.envs.utils import OpenRouterJury  # or from your local import
            jury_class = OpenRouterJury
        self._load_scenarios(scenarios_path) # Load scenarios
        self.judge = jury_class(jury_size=jury_size, options=["Player 0", "Player 1"]) # Initialize judges

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def _load_scenarios(self, scenarios_path: Optional[str]):
        try:
            if scenarios_path is not None: # Use provided path
                if not os.path.exists(scenarios_path): raise FileNotFoundError(f"Scenario data file not found at: {scenarios_path}")
                with open(scenarios_path, "r", encoding="utf-8") as file: self.scenarios = json.load(file)["scenarios"]
            else: # Use package resource
                with importlib.resources.files('textarena.envs.ScenarioPlanning').joinpath('scenarios.json').open('r') as file: self.scenarios = json.load(file)["scenarios"]
        except Exception as e: raise FileNotFoundError(f"Failed to load Scenarios data: {str(e)}")
        if not self.scenarios: raise ValueError("Scenarios list is empty.")

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=2, seed=seed)
        game_state = {"strategies": {0: None, 1: None}, "scenario": random.choice(self.scenarios), "votes": {0: {"Votes": 0}, 1: {"Votes": 0}}}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)

    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return (
            f"You are Player {player_id} in the Scenario Planning game.\nScenario: {game_state['scenario']}\n"
            "Your goal is to propose a strategy for survival in this scenario.\n"
            "After both players submit their strategies, a panel of judges will evaluate them.\n"
            "On your turn, simply type your strategy."
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.game_state["strategies"][player_id] = action # Store the strategy
        if all(strategy is not None for strategy in self.state.game_state["strategies"].values()): # check if both players have submitted their strategies
            votes = self._evaluate_strategies() # Conduct judging
            self.state.game_state["votes"] = {0: {"Votes": votes["Player 0"]}, 1: {"Votes": votes["Player 1"]}}
            if votes["Player 0"] == votes["Player 1"]: self.state.set_draw(reason="An equal number of judges voted for each option.") # check for draw first
            else:
                winner_id = 0 if votes["Player 0"] > votes["Player 1"] else 1 # get winner id
                self.state.set_winner(player_id=winner_id, reason=f"Player {winner_id} wins by convincing the judges.")
        return self.state.step()

    def _evaluate_strategies(self) -> Dict[str, int]:
        prompt = (
            f"Scenario: {self.state.game_state['scenario']}\n\nPlayer 0's Strategy:\n{self.state.game_state['strategies'][0]}\n\n"
            f"Player 1's Strategy:\n{self.state.game_state['strategies'][1]}\n\nBased on the above strategies, which player's strategy is more effective and feasible for survival?\n"
            f"Vote for 'Player 0' or 'Player 1'. Provide only the player you vote for."
        )
        return self.judge.evaluate(context=prompt)