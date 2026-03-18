import textarena as ta 
from textarena.core import ObservationWrapper, Env, Observations, Info, ObservationType
from typing import Dict, Optional, Tuple, List

__all__ = ["LLMObservationWrapper", "DiplomacyObservationWrapper", "FirstLastObservationWrapper", "FirstLastObservationWrapper"]


class LLMObservationWrapper(ObservationWrapper):
    """
    A wrapper for converting environment observations into formatted strings suitable
    for large language models (LLMs). It ensures that duplicate observations are not
    added to the full observations.
    """

    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        str_observation = ""
        
        if player_id in self.full_observations:
            for sender_id, message, _ in self.full_observations[player_id]:
                if sender_id == ta.GAME_ID:
                    sender_name = self.t("LLMObservationWrappers", "game")
                else:
                    sender_name = self.env.state.role_mapping.get(sender_id, self.t("LLMObservationWrappers", "player", sender_id=sender_id))
                str_observation += f"\n[{sender_name}] {message}"

        return str_observation

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        # Extend the full observations with the current observations without duplicates
        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        # Append new observations in sequence
        self.full_observations[player_id].extend(observation)

        return self._convert_obs_to_str(player_id=player_id)


    
class DiplomacyObservationWrapper(LLMObservationWrapper):
    def __init__(self, env: ta.Env):
        super().__init__(env)

    def _get_history_conversation(self, player_id: int) -> str:
        """ Get the history conversation for the given player. """
        history = []
        for sender_id, message, _ in self.full_observations[player_id][1:]:
            if sender_id == ta.GAME_ID:
                sender_name = self.t("LLMObservationWrappers", "game")
            else:
                sender_name = self.env.state.role_mapping.get(sender_id, self.t("LLMObservationWrappers", "player", sender_id=sender_id))
            history.append(f"[{sender_name}] {message}")
        return "\n".join(history)

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self.env.get_prompt(player_id, self._get_history_conversation(player_id))

        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        self.full_observations[player_id].extend(observation)

        return self.env.get_prompt(player_id, self._get_history_conversation(player_id))


class FirstLastObservationWrapper(ObservationWrapper):
    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        return_str = self.full_observations[player_id][0][1]
        if len(self.full_observations[player_id]) > 1:
            return_str += "\n\n" + self.full_observations[player_id][-1][1]

        return return_str + "\n\n" + self.t("LLMObservationWrappers", "next_action")

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        # Extend the full observations with the current observations without duplicates
        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        # Append new observations in sequence
        self.full_observations[player_id].extend(observation)

        return self._convert_obs_to_str(player_id=player_id)
    

class GameBoardObservationWrapper(ObservationWrapper):
    """ show the initial prompt and the most recent game board """
    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        prompt = [obs[1] for obs in self.full_observations[player_id] if obs[2] == ObservationType.PROMPT][0]
        last_board_state = [obs[1] for obs in self.full_observations[player_id] if obs[2] == ObservationType.GAME_BOARD][-1]
        assert prompt and last_board_state, f"You are using the GameBoardObservationWrapper, but either the ObservationType.PROMPT or ObservationType.GAME_BOARD is missing"
        return prompt + "\n\n" + last_board_state # + "\n\n" + "Next Action:"

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None: return self._convert_obs_to_str(player_id=player_id)
        # Extend the full observations with the current observations without duplicates
        if player_id not in self.full_observations: self.full_observations[player_id] = []
        self.full_observations[player_id].extend(observation) # Append new observations in sequence
        return self._convert_obs_to_str(player_id=player_id)

    


class GameMessagesObservationWrapper(ObservationWrapper):
    """ show the initial prompt and the messages sent by the game """
    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        str_observation = ""
        if player_id in self.full_observations:
            for _, message, observation_type in self.full_observations[player_id]:
                if observation_type not in [ObservationType.PLAYER_ACTION, ObservationType.GAME_ADMIN]: 
                    str_observation += f"\n {message}"
        return str_observation

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None: return self._convert_obs_to_str(player_id=player_id)
        # Extend the full observations with the current observations without duplicates
        if player_id not in self.full_observations: self.full_observations[player_id] = []
        self.full_observations[player_id].extend(observation) # Append new observations in sequence
        return self._convert_obs_to_str(player_id=player_id)

class GameMessagesAndCurrentBoardObservationWrapper(ObservationWrapper):
    """Show the initial prompt, game messages (excluding player actions), and current game board."""
    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str, ObservationType]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        str_observation = ""
        prompt = None
        board_state = None
        for _, message, obs_type in self.full_observations.get(player_id, []):
            if obs_type == ObservationType.PROMPT:
                prompt = message
            elif obs_type == ObservationType.GAME_BOARD:
                board_state = message
            elif obs_type not in [ObservationType.PLAYER_ACTION, ObservationType.GAME_ADMIN]:
                str_observation += f"\n{message}"

        if prompt is None or board_state is None:
            raise ValueError("Missing required observation types: PROMPT or GAME_BOARD")

        return f"{prompt}\n\n{str_observation.strip()}\n\n{board_state}" #\n\nNext Action:"

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        self.full_observations[player_id].extend(observation)
        return self._convert_obs_to_str(player_id=player_id)

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        self.full_observations[player_id].extend(observation)
        return self._convert_obs_to_str(player_id=player_id)

class SingleTurnObservationWrapper(ObservationWrapper):
    def __init__(self, env: Env):
        super().__init__(env)

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        return observation[0][1]



class SettlersOfCatanObservationWrapper(ObservationWrapper):
    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str, ObservationType]]] = {}

    def _convert_obs_to_str(self, player_id: int) -> Observations:
        idx_final_board = -1
        for i, (_, _, obs_type) in enumerate(self.full_observations.get(player_id, [])):
            if obs_type==ObservationType.GAME_BOARD: idx_final_board=i
        return_str = ""
        for i, (sender_id, message, obs_type) in enumerate(self.full_observations.get(player_id, [])):
            if sender_id == ta.GAME_ID: sender_name = self.t("LLMObservationWrappers", "game")
            else: sender_name = self.env.state.role_mapping.get(sender_id, self.t("LLMObservationWrappers", "player", sender_id=sender_id))

            if obs_type != ObservationType.GAME_BOARD:
                return_str += f"\n[{sender_name}]\t{message}"
            elif obs_type==ObservationType.GAME_BOARD and i==idx_final_board:
                return_str += f"\n{message}"
        return return_str


    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        self.full_observations[player_id].extend(observation)
        return self._convert_obs_to_str(player_id=player_id)

    def observation(self, player_id: int, observation: Optional[ta.Observations]):
        if observation is None:
            return self._convert_obs_to_str(player_id=player_id)

        if player_id not in self.full_observations:
            self.full_observations[player_id] = []

        self.full_observations[player_id].extend(observation)
        return self._convert_obs_to_str(player_id=player_id)