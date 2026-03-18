import random, copy
from typing import List, Dict, Tuple, Any, Optional, Callable

import textarena as ta


class SinglePlayerState(ta.State):
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None, error_allowance: Optional[int]=1):
        """
        Initialize the SinglePlayerState object.

        Args:
            num_players (int): The number of players in the game (asserts to 1 here)
            max_turns (Optional[int]): The maximum number of turns.
            error_allowance (Optional[int]): Number of errors allowed before a player loses the game.
            seed (Optional[int]): The random seed to be used
        """
        assert num_players==1, f"The number of players has to be 1, received {num_players}"

        self.max_turns = max_turns
        self.error_allowance = error_allowance
        super().__init__(num_players=num_players, seed=seed, max_turns=max_turns)

    def reset(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]=None, secret_roles: Optional[Dict[int, str]]=None):
        if role_mapping is None: role_mapping = {pid: self.t("SinglePlayerState", "player", pid=pid) for pid in range(self.num_players)}
        self.standard_resets(game_state=game_state, player_prompt_function=player_prompt_function, role_mapping=role_mapping, secret_roles=secret_roles)
        self.error_count = 0
        self.made_invalid_move = False

    def step(self):
        if not self.made_invalid_move:
            self.error_count = 0
            self.turn += 1 # increment turn counter
            self.game_info[self.current_player_id]["turn_count"] += 1 # increment player turn count
        if self.done: return (True, self.step_info)# if game happens to be terminated on last turn ...

        self.made_invalid_move = False # reset
        step_info = self.step_info 
        self.step_info = {} # reset info
        return (self.done, step_info)

    def set_outcome(self, reward: float, reason: Optional[str]=None):
        self.rewards = {0: reward}
        self.game_info[0]["reason"] = reason
        self.done = True

    def set_invalid_move(self, reason: Optional[str], reward: float=-1.0):
        if self.error_allowance > self.error_count:
            self.error_count += 1 # increment error count
            self.made_invalid_move = True
            self.add_observation(message=self.t("SinglePlayerState", "invalid_move", reason=reason), observation_type=ta.ObservationType.GAME_ADMIN)
        else:
            self.rewards = {0: reward}
            self.game_info[0]["reason"] = f"Invalid Move: {reason}"
            self.game_info[0]["invalid_move"] = True 
            self.done = True


class TwoPlayerState(ta.State):
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None, error_allowance: Optional[int]=1):
        """
        Initialize the TwoPlayerState object.

        Args:
            num_players (int): The number of players in the game (asserts to 2 here)
            max_turns (Optional[int]): The maximum number of turns.
            error_allowance (Optional[int]): Number of errors allowed before a player loses the game.
            seed (Optional[int]): The random seed to be used
        """
        assert num_players==2, f"The number of players has to be 2, received {num_players}"

        self.max_turns = max_turns
        self.error_allowance = error_allowance
        super().__init__(num_players=num_players, seed=seed, max_turns=max_turns)

    def reset(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]=None, secret_roles: Optional[Dict[int, str]]=None):
        if role_mapping is None: role_mapping = {pid: self.t("MultiPlayerState", "player", pid=pid) for pid in range(self.num_players)}
        self.standard_resets(game_state=game_state, player_prompt_function=player_prompt_function, role_mapping=role_mapping, secret_roles=secret_roles)
        self.error_count = 0
        self.made_invalid_move = False

    def step(self, rotate_player: bool=True):
        if not self.made_invalid_move:
            self.error_count = 0
            self.turn += 1 # increment turn counter
            self.game_info[self.current_player_id]["turn_count"] += 1 # increment player turn count

        if self.done: 
            return (True, self.step_info)# if game happens to be terminated on last turn ...

        if rotate_player and not self.made_invalid_move:
            self.current_player_id = 1-self.current_player_id
            self.error_count = 0

        self.made_invalid_move = False # reset
        step_info = self.step_info 
        self.step_info = {} # reset info
        return (self.done, step_info)

    def manually_set_current_player_id(self, new_player_id: int):
        if not self.made_invalid_move:
            self.current_player_id = new_player_id
            self.error_count = 0

    def set_winner(self, player_id: int, reason: str):
        self.rewards = {player_id: 1, 1-player_id: -1}
        for pid in range(2): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_winners(self, player_ids: List[int], reason: str):
        self.rewards = {pid: (1 if pid in player_ids else -1) for pid in range(self.num_players)}
        self.info["reason"] = reason
        self.info["turn_count"] = self.turn + 1 # finished on the (n+1)th turn
        self.info["end_by_invalid"] = False
        self.done = True

    def set_draw(self, reason: str):
        self.rewards = {0: 0, 1: 0}
        for pid in range(2): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_invalid_move(self, reason: str):
        if self.error_allowance > self.error_count:
            self.error_count += 1 # increment error count
            self.made_invalid_move = True
            self.add_observation(to_id=self.current_player_id, message=self.t("MultiPlayerState", "invalid_move", current_player_id=self.current_player_id, reason=reason), observation_type=ta.ObservationType.GAME_ADMIN)
        else:
            self.rewards = {self.current_player_id: -1, 1-self.current_player_id: 1}
            for pid in range(2): self.game_info[pid]["reason"] = reason
            self.game_info[self.current_player_id]["invalid_move"] = True
            self.done = True

class FFAMultiPlayerState(ta.State):
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None, error_allowance: Optional[int]=1):
        """
        Initialize the FFAMultiPlayerState object.

        Args:
            num_players (int): The number of players in the game (asserts to 2 here)
            max_turns (Optional[int]): The maximum number of turns.
            error_allowance (Optional[int]): Number of errors allowed before a player loses the game.
            seed (Optional[int]): The random seed to be used
        """
        self.max_turns = max_turns
        self.error_allowance = error_allowance
        super().__init__(num_players=num_players, seed=seed, max_turns=max_turns)

    def reset(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]=None, secret_roles: Optional[Dict[int, str]]=None):
        if role_mapping is None: role_mapping = {pid: self.t("MultiPlayerState", "player", pid=pid) for pid in range(self.num_players)}
        self.standard_resets(game_state=game_state, player_prompt_function=player_prompt_function, role_mapping=role_mapping, secret_roles=secret_roles)
        self.error_count = 0
        self.made_invalid_move = False
        self.elimination_order = []
        self.end_by_invalid = False

    def step(self, rotate_player: bool=True):
        if not self.made_invalid_move:
            self.error_count = 0
            self.turn += 1
            self.game_info[self.current_player_id]["turn_count"] += 1 # increment player turn count

        if self.done: 
            return (True, self.step_info)

        if rotate_player and not self.made_invalid_move:
            self.current_player_id = (self.current_player_id + 1) % self.num_players
            while self.current_player_id in self.elimination_order:
                self.current_player_id = (self.current_player_id + 1) % self.num_players
            self.error_count = 0

        self.made_invalid_move = False
        step_info = self.step_info
        self.step_info = {}
        return (self.done, step_info)


    def manually_set_current_player_id(self, new_player_id: int, force: bool = False):
        if (not self.made_invalid_move) or force:
            self.current_player_id = new_player_id
            self.error_count = 0

    def add_elimination(self, pid: int):
        self.elimination_order.append(pid)

    def is_player_alive(self, pid: int) -> bool:
        return pid not in self.elimination_order

    def next_alive_player(self, predicate: Optional[Callable[[int], bool]] = None) -> Optional[int]:
        """
        Return the next player clockwise who…

        * has NOT been eliminated         (always checked), and
        * satisfies `predicate(pid)`      (if a predicate is supplied).

        If no such player exists, return **None**.
        """
        start = (self.current_player_id + 1) % self.num_players
        pid = start
        while pid != self.current_player_id:
            alive = pid not in self.elimination_order
            ok = predicate(pid) if predicate is not None else True
            if alive and ok:
                return pid
            pid = (pid + 1) % self.num_players
        return None  # nobody qualifies

    def set_game_outcome(self, reward_dict: Dict[int, float], reason: str):
        self.rewards = reward_dict
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_winners(self, player_ids: List[int], reason: str):
        self.rewards = {pid: (1 if pid in player_ids else -1) for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_draw(self, reason: str):
        self.rewards = {pid: 0 for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_invalid_move(self, reason: str) -> bool:
        self.made_invalid_move = True
        if self.error_allowance > self.error_count:
            self.error_count += 1
            self.add_observation(to_id=self.current_player_id, message=self.t("MultiPlayerState", "invalid_move", current_player_id=self.current_player_id, reason=reason), observation_type=ta.ObservationType.GAME_ADMIN)
            return False
        else:
            self.elimination_order.append(self.current_player_id)
            self.error_count = 0
            self.game_info[self.current_player_id]["invalid_move"] = True
            return True


class TeamMultiPlayerState(ta.State):
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None, error_allowance: Optional[int]=1):
        """
        Initialize the TeamMultiPlayerState object.

        Args:
            num_players (int): The number of players in the game (asserts to 2 here)
            max_turns (Optional[int]): The maximum number of turns.
            error_allowance (Optional[int]): Number of errors allowed before a player loses the game.
            seed (Optional[int]): The random seed to be used
        """
        self.max_turns = max_turns
        self.error_allowance = error_allowance
        super().__init__(num_players=num_players, seed=seed, max_turns=max_turns)

    def reset(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]=None, secret_roles: Optional[Dict[int, str]]=None):
        if role_mapping is None: role_mapping = {pid: self.t("MultiPlayerState", "player", pid=pid) for pid in range(self.num_players)}
        self.standard_resets(game_state=game_state, player_prompt_function=player_prompt_function, role_mapping=role_mapping, secret_roles=secret_roles)
        self.error_count = 0
        self.made_invalid_move = False
        self.end_by_invalid = False

    def step(self, rotate_player: bool=False):
        if not self.made_invalid_move:
            self.error_count = 0
            self.turn += 1

        if self.done: 
            return (True, self.step_info)

        self.made_invalid_move = False
        step_info = self.step_info
        self.step_info = {}
        return (self.done, step_info)

    def manually_set_current_player_id(self, new_player_id: int):
        if not self.made_invalid_move:
            self.current_player_id = new_player_id
            self.error_count = 0

    def set_winners(self, player_ids: List[int], reason: str):
        self.rewards = {pid: (1 if pid in player_ids else -1) for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_draw(self, reason: str):
        self.rewards = {pid: 0 for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_invalid_move(self, reason: str) -> bool:
        self.made_invalid_move = True
        if self.error_allowance > self.error_count:
            self.error_count += 1
            self.add_observation(to_id=self.current_player_id, message=self.t("MultiPlayerState", "invalid_move", current_player_id=self.current_player_id, reason=reason), observation_type=ta.ObservationType.GAME_ADMIN)
            return False
        else: # player made repeated invalid moves. Up to the environment how this should be handled
            self.game_info[self.current_player_id]["invalid_move"] = True
            return True



class MinimalMultiPlayerState(ta.State):
    def __init__(self, num_players: int, seed: Optional[int]=None, max_turns: Optional[int]=None, error_allowance: Optional[int]=1):
        """
        Initialize the MinimalMultiPlayerState object.

        Args:
            num_players (int): The number of players in the game (asserts to 2 here)
            max_turns (Optional[int]): The maximum number of turns.
            error_allowance (Optional[int]): Number of errors allowed before a player loses the game.
            seed (Optional[int]): The random seed to be used
        """
        self.max_turns = max_turns
        self.error_allowance = error_allowance
        super().__init__(num_players=num_players, seed=seed, max_turns=max_turns)

    def reset(self, game_state: Optional[Dict[str, Any]]=None, player_prompt_function: Optional[Callable]=None, role_mapping: Optional[Dict[int, str]]=None, secret_roles: Optional[Dict[int, str]]=None):
        if role_mapping is None: role_mapping = {pid: self.t("MultiPlayerState", "player", pid=pid) for pid in range(self.num_players)}
        self.standard_resets(game_state=game_state, player_prompt_function=player_prompt_function, role_mapping=role_mapping, secret_roles=secret_roles)
        self.error_count = 0
        self.made_invalid_move = False

    def step(self, rotate_player: bool=True):
        if not self.made_invalid_move:
            self.error_count = 0
            self.turn += 1
            self.game_info[self.current_player_id]["turn_count"] += 1 # increment player turn count

        if self.done: return (True, self.step_info)
        self.made_invalid_move = False
        step_info = self.step_info
        self.step_info = {}
        return (self.done, step_info)

    def manually_set_current_player_id(self, new_player_id: int, force: bool = False):
        if (not self.made_invalid_move) or force:
            self.current_player_id = new_player_id
            self.error_count = 0

    def set_game_outcome(self, reward_dict: Dict[int, float], reason: str):
        self.rewards = reward_dict
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_winners(self, player_ids: List[int], reason: str):
        self.rewards = {pid: (1 if pid in player_ids else -1) for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_draw(self, reason: str):
        self.rewards = {pid: 0 for pid in range(self.num_players)}
        for pid in range(self.num_players): self.game_info[pid]["reason"] = reason
        self.done = True

    def set_invalid_move(self, reason: str) -> bool:
        self.made_invalid_move = True
        if self.error_allowance > self.error_count:
            self.error_count += 1
            self.add_observation(to_id=self.current_player_id, message=self.t("MultiPlayerState", "invalid_move", current_player_id=self.current_player_id, reason=reason), observation_type=ta.ObservationType.GAME_ADMIN)
            return False
        else:
            # self.elimination_order.append(self.current_player_id)
            self.error_count = 0
            self.game_info[self.current_player_id]["invalid_move"] = True
            return True