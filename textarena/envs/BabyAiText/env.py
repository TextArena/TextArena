from typing import Any, Dict, Optional, Tuple

import textarena as ta
from copy import deepcopy

try:
    import gym
except ImportError:
    raise ImportError(
        "gym-minigrid package is required for BabyAiText. "
        "Follow the installation instructions at "
        "https://github.com/flowersteam/Grounding_LLMs_with_online_RL/tree/main/babyai-text"
    )

try:
    import babyai_text
except ImportError:
    raise ImportError(
        "BabyAI-Text package is required for BabyAiText. "
        "Follow the installation instructions at "
        "https://github.com/flowersteam/Grounding_LLMs_with_online_RL/tree/main/babyai-text"
    )

from babyai.bot import Bot


class BabyAiTextEnv(ta.Env):
    """Environment for BabyAI-text game"""

    def __init__(self, env_name: str = "BabyAI-MixedTestLocal-v0", max_turns: int = 20, seed: Optional[int] = None) -> None:
        """
        Initialize the 'BabyAI-Text' game environment.

        Args:
            env_name (str): The name of the environment, currently supported are: BabyAI-MixedTestLocal-v0,
            BabyAI-MixedTrainLocal-v0.
            max_turns (int)
        """
        self.max_turns = max_turns
        self.name_environment = env_name
        self.baby_ai_text_env = gym.make(env_name, seed=seed)
        self.seed = seed
        self.action_space = ["turn left", "turn right", "go forward", "pick up", "drop", "toggle"]

    def reset(self, num_players: int, seed: Optional[int]=None) -> None:
        """ Reset the 'BabyAI-Text' game to its initial state """
        # Initialize game state variables
        self.baby_ai_text_env.seed(seed if seed is not None else self.seed)
        binary_state, text_state = self.baby_ai_text_env.reset()
        self.state = ta.State(num_players=num_players, min_players=1, max_players=1, max_turns=self.max_turns)
        self.state.reset(
            seed=seed,
            game_state=binary_state | text_state,
            player_prompt_function=self._generate_player_prompt
        )

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        """ Generate the initial prompt for the player, providing them with their goal and available actions """
        descriptions = ". ".join(game_state["descriptions"])
        actions = ", ".join(self.action_space)
        prompt = (
            f"You are playing 'BabyAI-Text'.\n"
            f"Your goal is to {game_state['mission']}.\n"
            f"Available actions are {actions}.\n"
            f"{descriptions} \n"
            "On your turn, simply type your message.\n"
        )
        if self.state.max_turns:
            prompt += f"The game lasts for {self.state.max_turns} turns in total.\n"
        return prompt

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """ Process the player's action """
        player_id = self.state.current_player_id

        # update the observations and log the action
        self.state.add_observation(from_id=player_id, to_id=-1, message=action)
        try:
            action_id = self.action_space.index(action)
        except ValueError:
            observation = "Invalid action"
            self.state.add_observation(from_id=-1, to_id=player_id, message=observation)
            return (False, {'observations': observation, 'reward': -1, 'info': {}})

        obs, reward, done, info = self.baby_ai_text_env.step(action_id)
        new_description = ". ".join(info["descriptions"])
        self.state.add_observation(from_id=-1, to_id=player_id, message=new_description)
        self.state.info = {'observations': obs, 'reward': reward, 'info': info}
        self.state.done = done

        return self.state.step()

    def get_board_str(self):
        return (f"Goal:{self.baby_ai_text_env.mission}\n" +
                str(self.baby_ai_text_env.env.env) + f"\nInventory: {self.get_inventory()}\nTurn:{self.state.turn}")

    def gold_path(self):
        try:
            env_copy = deepcopy(self.baby_ai_text_env)
            bot = Bot(env_copy)
            actions = []
            done = False
            action = None
            while not done:
                try:
                    action = bot.replan(action)
                    if str(action) == 'Actions.done':
                        break
                    action_int = int(action)
                    actions.append(self.action_space[action_int])
                    obs, reward, done, info = env_copy.step(action_int)
                except Exception as e:
                    print(f"Error in getting gold paths: {e}")
                    break

        except Exception as e:
            print(f"Error in getting gold paths: {e}")

        return actions

    def get_inventory(self):
        if self.baby_ai_text_env.carrying is not None:
            return f"{self.baby_ai_text_env.carrying.color} {self.baby_ai_text_env.carrying.type}"