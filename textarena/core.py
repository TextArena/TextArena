import copy
import re
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, List, Tuple, Optional


def extract_action(text: str) -> str:
    """Extract the final action from a model response.

    Models are instructed to put the action they want to submit inside
    <action>...</action> tags; the content of the last non-empty tag is what
    gets passed to `env.step`. If no tags are present, the raw text is used.
    """
    matches = re.findall(r"<action>(.*?)</action>", text, re.DOTALL | re.IGNORECASE)
    for match in reversed(matches):
        if match.strip():
            return match.strip()
    return text.strip()

class ObservationType(Enum):
    PROMPT = auto() # the player prompts
    PLAYER_ACTION = auto() # a player submitting an action 
    GAME_ACTION_DESCRIPTION = auto() # the game describing a player action
    GAME_MESSAGE = auto() # minor game messages not directly dependent on actions
    GAME_BOARD = auto() # the actual game-board visualization
    GAME_ADMIN = auto() # invalid moves, win/loss, etc.


GAME_ID = -1  # literal for use in game messages
Message = Tuple[int, str, ObservationType]  # maps role to content
Observations = List[Message]  # messages newly visible to the acting player
Rewards = Dict[int, float]  # maps player ID to reward
Info = Dict[str, Any]  # additional information about the environment


class Env(ABC):
    """
    Abstract base class for text-based game environments.

    This class outlines the interface for the environment, including methods for resetting the environment,
    stepping through the environment (taking actions), and rendering the environment state.
    """
    state: Any

    @abstractmethod
    def reset(self, num_players: int, seed: Optional[int]=None):
        """
        Resets the environment to an initial state.

        Args:
            num_players (int): Number of players in the game.
            seed (Optional[int]): Seed for the random number generator to ensure reproducibility.
        """
        raise NotImplementedError

    @abstractmethod
    def step(self, action: str) -> Tuple[bool, Info]:
        """
        Performs a single step in the environment.

        Args:
            player_id (int): The ID of the player taking the action.
            action (str): The action to be taken by the player.

        Returns:
            Tuple containing:
                - done (bool): Whether the episode has concluded
                - info (Dict[str, Any]): Additional information about the environment.
        """
        raise NotImplementedError

    def get_observation(self):
        return self.state.current_player_id, self.state.get_current_player_observation()

    def close(self):
        rewards = self.state.close()
        return rewards

class Wrapper(Env):
    """ Base class for environment wrappers. """
    def __init__(self, env):
        # Confirm we are not double-wrapping with the same wrapper type
        if isinstance(env, Wrapper) and env.is_wrapped_with(type(self)):
            raise ValueError(f"Environment is already wrapped with {type(self).__name__}. Double-wrapping is not allowed.")
        self.env = env

    def __getattr__(self, name):
        return getattr(self.env, name)

    def reset(self, num_players: int , seed: Optional[int] = None):
        return self.env.reset(num_players=num_players, seed=seed)

    def step(self, action: str) -> Tuple[bool, Info]:
        return self.env.step(action=action)

    def get_observation(self):
        return self.env.get_observation()

    def close(self):
        return self.env.close()

    def snapshot(self):
        """Capture the wrapped environment and this wrapper's mutable state."""
        wrapper_state = {
            name: copy.deepcopy(value)
            for name, value in self.__dict__.items()
            if name != "env"
        }
        return {"env": self.env.snapshot(), "wrapper": wrapper_state}

    def restore(self, snapshot):
        """Restore a snapshot produced by this wrapper."""
        if "wrapper" not in snapshot:
            return self.env.restore(snapshot)
        self.env.restore(snapshot["env"])
        for name in tuple(self.__dict__):
            if name != "env":
                del self.__dict__[name]
        self.__dict__.update(copy.deepcopy(snapshot["wrapper"]))

    def __deepcopy__(self, memo):
        import copy
        copied_env = copy.deepcopy(self.env, memo) # Deepcopy the wrapped environment
        cls = self.__class__ # Create a new wrapper of the same type
        copied_wrapper = cls(copied_env)
        for k, v in self.__dict__.items(): # Copy any other attributes (excluding .env)
            if k != "env":
                setattr(copied_wrapper, k, copy.deepcopy(v, memo))
        return copied_wrapper

    def is_wrapped_with(self, wrapper_class: type) -> bool:
        env = self
        while isinstance(env, Wrapper):
            if isinstance(env, wrapper_class):
                return True
            env = env.env
        return False


class ObservationWrapper(Wrapper):
    def get_observation(self):
        player_id, observation = self.env.get_observation()
        return player_id, self.observation(player_id, observation)
    
    def observation(self):
        raise NotImplementedError


class RenderWrapper(Wrapper):
    def step(self, action: str) -> Tuple[bool, Optional[Info]]:
        return self.env.step(action=action)
    
    def reset(self, num_players: int , seed: Optional[int] = None):
        self.reset_render()
        return self.env.reset(num_players=num_players, seed=seed)

    def reset_render(self):
        raise NotImplementedError


class ActionWrapper(Wrapper):
    def step(self, action: str) -> Tuple[bool, Optional[Info]]:
        return self.env.step(action=self.action(action))

    def action(self, action: str) -> str:
        raise NotImplementedError


class Agent(ABC):
    """ Generic agent class that defines the basic structure of an agent """
    @abstractmethod
    def __call__(self, observation: str) -> str:
        """
        Process the observation and return the action.

        Args:
            observation (str): The input string to process.

        Returns:
            str: The response generated by the agent.
        """
        pass


class AgentWrapper(Agent):
    """ TODO """
    def __init__(self, agent: Agent):
        """ TODO """
        self.agent = agent 
        assert isinstance(agent, Agent)

    def __getattr__(self, name):
        """ TODO """
        return getattr(self.agent, name)

    def __call__(self, observation: str) -> str:
        return self.agent(observation=observation)




