import random
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, List, Tuple, Optional, Callable

class ObservationType(Enum):
    PROMPT = auto() # the player prompts
    PLAYER_ACTION = auto() # a player submitting an action 
    GAME_ACTION_DESCRIPTION = auto() # the game describing a player action
    GAME_MESSAGE = auto() # minor game messages not directly dependent on actions
    GAME_BOARD = auto() # the actual game-board visualization
    GAME_ADMIN = auto() # invalid moves, win/loss, etc.


GAME_ID = -1  # literal for use in game messages
Message = Tuple[int, str, ObservationType]  # maps role to content
Observations = dict[int, List[Message]]  # consists of the message seen by each player after the action
Rewards = Dict[int, int]  # maps player ID to reward
Info = Dict[str, Any]  # additional information about the environment


class State:
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None):
        if seed is not None: random.seed(seed) # set the random seed
        self.max_turns = max_turns 
        self.num_players = num_players
        self.current_player_id = 0

    def check_turn_limit(self):
        return self.turn >= self.max_turns and self.done == False

    def update_current_player_id(self, player_id: int):
        assert player_id in self.role_mapping, f"Tried to update current player to {player_id}, which does not exist. Available players: {list(self.role_mapping.keys())}"

    def standard_resets(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]={}, secret_roles: Optional[Dict[int, str]]=None):
        self.game_state = game_state
        self.role_mapping = role_mapping
        
        # reset standard game parameters
        self.turn = 0
        self.done = False 
        self.step_info = {} # returned and reset every step.
        self.game_info = {pid: {"role": f"Player {pid}", "invalid_move": False, "turn_count": 0} for pid in range(self.num_players)} # returned at the end of the game
        # the role is intentionally a string so ppl don't use it as an index for role advantage calculation, as some environments will return str based roles and then crash their code
        # invalid moves should be returned on a per-player basis since in most multiplayer games an invalid move won't end the game
        # same with the turn-count. It's not always symmetric, so no point having a global one, esp. for multiplayer games.
        if secret_roles is not None:
            for pid, role in secret_roles.items():
                self.game_info[pid]["role"] = role # important for RL training on games like secret mafia
                
        self.observations = {pid: [] for pid in range(self.num_players)}
        self.rewards = None
        self.logs = []

        # set role mapping
        if self.role_mapping is None:
            for pid in range(self.num_players):
                self.role_mapping[pid] = f"Player {pid}"
        self.role_mapping[GAME_ID] = self.role_mapping.get(GAME_ID, "GAME") # add if not provided

        # generate the player prompts
        if player_prompt_function is not None:
            for player_id in range(self.num_players):
                self.add_observation(to_id=player_id, message=player_prompt_function(player_id=player_id, game_state=self.game_state), observation_type=ObservationType.PROMPT)

    def add_observation(self, message: str, observation_type: ObservationType, from_id: int=GAME_ID, to_id: int=-1):
        if observation_type==ObservationType.PLAYER_ACTION:
            for role_tag in self.role_mapping.values(): message = message.replace(f"[{role_tag}]", "") # filter out role tags from message
        self.logs.append((from_id, message))
        if to_id == -1:
            for pid in range(self.num_players):
                self.observations[pid].append((from_id, message, observation_type))
        else:
            assert to_id in self.observations, f"The provided 'to_id' {to_id} does not exists. ({list(self.observations.keys())})"
            self.observations[to_id].append((from_id, message, observation_type))

    def get_current_player_observation(self):
        current_player_observation = self.observations[self.current_player_id]
        self.observations[self.current_player_id] = []
        return current_player_observation

    def step(self):
        if self.done: return (True, self.step_info)# if game happens to be terminated on last turn ...
        self.turn += 1 # increment turn counter
        step_info = self.step_info 
        self.step_info = {} # reset info
        return (self.done, step_info)

    def close(self):
        return self.rewards, self.game_info


class Env(ABC):
    """
    Abstract base class for text-based game environments.

    This class outlines the interface for the environment, including methods for resetting the environment,
    stepping through the environment (taking actions), and rendering the environment state.
    """
    game_state: State  # the state of the environment

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

    def reset(self, num_players: int, seed: Optional[int] = None, **kwargs: Any):
        return self.env.reset(num_players=num_players, seed=seed, **kwargs)

    def step(self, action: str) -> Tuple[bool, Info]:
        return self.env.step(action=action)

    def get_observation(self):
        return self.env.get_observation()

    def close(self):
        return self.env.close()

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
    
    def reset(self, num_players: int, seed: Optional[int] = None, **kwargs: Any):
        self.reset_render()
        return self.env.reset(num_players=num_players, seed=seed, **kwargs)

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




