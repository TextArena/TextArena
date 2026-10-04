import importlib.resources
import inspect
import json
import math
import os
from numbers import Real
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.ScenarioPlanning.renderer import create_board_str

class ScenarioPlanningEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    snapshot_excluded_attributes = ("judge",)
    max_strategy_chars = 10_000
    max_jury_size = 100

    jury_size = ta.Param(5, "The number of judges.", min=1, max=max_jury_size)
    jury_class = ta.Param(
        None, "The class or factory called with `options` and `jury_size` (and the env's seeded `rng` if it accepts "
              "one). The object it returns must provide `evaluate(context)` returning "
              "`{\"Player 0\": votes, \"Player 1\": votes}`. None uses `OpenRouterJury`.",
        type=object, check=callable, rule="a callable",
    )
    scenarios_path = ta.Param(
        None, "A JSON file of the form `{\"scenarios\": [\"...\", ...]}` with unique, non-empty scenarios. None uses "
              "the bundled `scenarios.json`.", type=str,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.jury_class is None:
            from textarena.utils import OpenRouterJury
            self._jury_class = OpenRouterJury
        else:
            self._jury_class = self.jury_class
        self._load_scenarios(self.scenarios_path)
        self.judge = None
        self.max_turns = 2

    def get_board_str(self): return create_board_str(game_state=self.game_state)
    def _load_scenarios(self, scenarios_path: Optional[str]):
        try:
            if scenarios_path is not None:
                if not os.path.exists(scenarios_path):
                    raise FileNotFoundError(f"Scenario data file not found at: {scenarios_path}")
                with open(scenarios_path, "r", encoding="utf-8") as file:
                    payload = json.load(file)
            else:
                with importlib.resources.files("textarena.envs.ScenarioPlanning").joinpath(
                    "scenarios.json"
                ).open("r", encoding="utf-8") as file:
                    payload = json.load(file)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load scenarios data: {exc}") from exc
        self.scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
        if (
            not isinstance(self.scenarios, list)
            or not self.scenarios
            or any(not isinstance(scenario, str) or not scenario.strip() for scenario in self.scenarios)
            or len({scenario.strip().casefold() for scenario in self.scenarios}) != len(self.scenarios)
        ):
            raise ValueError("Scenarios data must contain a non-empty list of unique, non-empty strings.")

    def setup(self) -> Dict[str, Any]:
        self.judge = None
        return {"strategies": {0: None, 1: None}, "scenario": self.rng.choice(self.scenarios), "votes": {0: {"Votes": 0}, 1: {"Votes": 0}}}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in the Scenario Planning game.\nScenario: {self.game_state['scenario']}\n"
            "Your goal is to propose a strategy for survival in this scenario.\n"
            f"Each player submits exactly one strategy (Player 0 first), at most {self.max_strategy_chars} characters; "
            "the other player never sees it.\n"
            f"After both players submit their strategies, a panel of {self.jury_size} AI judges votes for the more "
            "effective and feasible one. The strategy with more votes wins; equal votes are a draw.\n"
            "On your turn, simply type your strategy."
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # an echo would show the strategy to the opponent

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(action, str) or not action.strip():
            return self.invalid("A strategy must contain non-whitespace text.")
        if len(action) > self.max_strategy_chars:
            return self.invalid(f"Strategies are limited to {self.max_strategy_chars} characters.")
        gs = self.game_state
        proposed_strategies = dict(gs["strategies"])
        proposed_strategies[player_id] = action.strip()
        if all(strategy is not None for strategy in proposed_strategies.values()):
            rng_state = self.rng.getstate()
            try:
                votes = self._evaluate_strategies(proposed_strategies)
            except Exception:
                self.rng.setstate(rng_state)
                self.judge = None
                return self.retryable("The jury could not evaluate the strategies.")
            gs["strategies"] = proposed_strategies
            gs["votes"] = {0: {"Votes": votes["Player 0"]}, 1: {"Votes": votes["Player 1"]}}
            if votes["Player 0"] == votes["Player 1"]: return self.draw(reason="An equal number of judges voted for each option.") # check for draw first
            winner_id = 0 if votes["Player 0"] > votes["Player 1"] else 1 # get winner id
            return self.winner(winner_id, reason=f"Player {winner_id} wins by convincing the judges.")
        gs["strategies"] = proposed_strategies
        return None

    def _evaluate_strategies(self, strategies: Dict[int, str]) -> Dict[str, float]:
        prompt = (
            f"Scenario: {self.game_state['scenario']}\n\nPlayer 0's Strategy:\n{strategies[0]}\n\n"
            f"Player 1's Strategy:\n{strategies[1]}\n\nBased on the above strategies, which player's strategy is more effective and feasible for survival?\n"
            f"Vote for 'Player 0' or 'Player 1'. Provide only the player you vote for."
        )
        votes = self.ask(self._ask_jury, prompt)
        expected = {"Player 0", "Player 1"}
        if not isinstance(votes, dict) or set(votes) != expected:
            raise ValueError("jury result must contain exactly Player 0 and Player 1.")
        if any(
            isinstance(vote, bool)
            or not isinstance(vote, Real)
            or not math.isfinite(float(vote))
            or vote < 0
            for vote in votes.values()
        ):
            raise ValueError("jury votes must be finite non-negative numbers.")
        vote_total = sum(float(vote) for vote in votes.values())
        if not math.isfinite(vote_total) or not 0 < vote_total <= self.jury_size:
            raise ValueError("jury vote total must be positive, finite, and no larger than jury_size.")
        return votes

    def _ask_jury(self, prompt: str) -> Dict[str, float]:
        jury_kwargs = {
            "jury_size": self.jury_size,
            "options": ["Player 0", "Player 1"],
        }
        try:
            parameters = inspect.signature(self._jury_class).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        if any(
            parameter.name == "rng" or parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        ):
            jury_kwargs["rng"] = self.rng
        self.judge = self._jury_class(**jury_kwargs)
        return self.judge.evaluate(context=prompt)
