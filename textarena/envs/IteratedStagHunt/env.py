import re
import numpy as np
from typing import Dict, Any, Optional, Tuple

import textarena as ta
# from textarena.envs.IteratedStagHunt.renderer import create_board_str


class IteratedStagHuntEnv(ta.Env):
    def __init__(self, num_rounds: int=5, conversation_rounds: int=3, mutual_stag_reward: int=10, single_hare_reward: int=8, single_stag_reward: int=1, mutual_hare_reward: int=5, randomize_payoff: bool=False):
        self.num_rounds = num_rounds
        self.conversation_rounds = conversation_rounds
        
        # payoffs
        self.mutual_stag_reward = mutual_stag_reward
        self.single_hare_reward = single_hare_reward
        self.single_stag_reward = single_stag_reward
        self.mutual_hare_reward = mutual_hare_reward
        self.randomize_payoff = randomize_payoff

        # Action patterns
        self.stag_pattern = re.compile(r"\[Stag\]", re.IGNORECASE)
        # self.hare_pattern = re.compile(r"\[Hare\]", re.IGNORECASE)

        self.curr_payoff: Dict[str, int] = {}


    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {
            "round": 1, "num_rounds": self.num_rounds, "phase": "conversation", "conversation_round": 0, "total_conversation_rounds": self.conversation_rounds, 
            "decisions": {0: None, 1: None}, "total_payoff": {0: 0, 1: 0}
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._create_round_payoff_matrix() 
    
    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Generate the initial prompt for a player."""
        return self.m(
            "player_prompt", "intro",
            player_id=player_id, num_rounds=game_state['num_rounds'],
            decision_rounds=self.num_rounds, conversation_rounds=game_state['total_conversation_rounds']
        )
    
    def _create_round_payoff_matrix(self) -> None:
        if not self.randomize_payoff:
            self.mutual_stag_payoff = self.mutual_stag_reward
            self.single_stag_payoff = self.single_stag_reward
            self.single_hare_payoff = self.single_hare_reward
            self.mutual_hare_payoff = self.mutual_hare_reward
        else:
            self.single_stag_payoff = self.single_stag_reward
            self.mutual_hare_payoff = np.random.randint(self.single_stag_payoff+1, self.mutual_hare_reward+1)
            self.single_hare_payoff = np.random.randint(self.mutual_hare_payoff, self.single_hare_reward+1)
            self.mutual_stag_payoff = np.random.randint(self.single_hare_payoff+1, self.mutual_stag_reward+1)

        message = self.m(
            "round", "payoff_matrix",
            round=self.state.game_state['round'],
            mutual_stag=self.mutual_stag_payoff, mutual_hare=self.mutual_hare_payoff,
            single_hare=self.single_hare_payoff, single_stag=self.single_stag_payoff,
            conversation_rounds=self.state.game_state['total_conversation_rounds']
        )
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)

    def step(self, action: str) -> Tuple[bool, Dict]:
        self.state.add_observation(to_id=self.state.current_player_id, from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        # check what phase we are in
        match self.state.game_state["phase"]:
            case "conversation":    self._handle_conversation_phase(action=action)
            case "decision":        self._handle_decision_phase(action=action)
        return self.state.step()

    def _handle_conversation_phase(self, action: str):
        # broadcast player action to opponent
        self.state.add_observation(to_id=1-self.state.current_player_id, from_id=self.state.current_player_id, message=action.strip(), observation_type=ta.ObservationType.PLAYER_ACTION)

        # only increment conversation round on player 1
        if self.state.current_player_id == 1:
            self.state.game_state["conversation_round"] += 1

            # check if we have completed all conversation rounds
            if self.state.game_state["conversation_round"] >= self.state.game_state["total_conversation_rounds"]:
                self.state.game_state["phase"] = "decision" # rotate phase
                self.state.add_observation(message=self.m("round", "decision_phase", round=self.state.game_state['round']), observation_type=ta.ObservationType.GAME_BOARD) # send decision prompt to everybody

    def _handle_decision_phase(self, action: str):
        # extraction decision
        self.state.game_state["decisions"][self.state.current_player_id] = "stag" if self.stag_pattern.search(action) else "hare" # hare if no stag pattern found
        
        # check if we have both decisions
        if all(decision is not None for decision in self.state.game_state["decisions"].values()):
            # determine pay-off & send message
            round_payoffs = [None, None]
            if self.state.game_state["decisions"][0] == self.state.game_state["decisions"][1]: # matching decision 
                round_payoffs[0] = round_payoffs[1] = (self.mutual_stag_payoff if self.state.game_state["decisions"][0]=="stag" else self.mutual_hare_payoff)
            else: # differing decisions
                round_payoffs[0] = self.single_stag_payoff if self.state.game_state["decisions"][0]=="stag" else self.single_hare_payoff
                round_payoffs[1] = self.single_stag_payoff if self.state.game_state["decisions"][1]=="stag" else self.single_hare_payoff
            
            for pid in [0,1]:
                self.state.game_state['total_payoff'][pid] += round_payoffs[pid]
            message = self.m(
                "round", "results",
                round=self.state.game_state['round'],
                decision0=self.state.game_state["decisions"][0], payoff0=round_payoffs[0], total0=self.state.game_state['total_payoff'][0],
                decision1=self.state.game_state["decisions"][1], payoff1=round_payoffs[1], total1=self.state.game_state['total_payoff'][1]
            )
            self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)


            # start next round
            self.state.game_state["round"] += 1
            self.state.game_state["phase"] = "conversation"; self.state.game_state["conversation_round"] = 0; self.state.game_state["decisions"] = {0: None, 1: None} # reset
            self._create_round_payoff_matrix()
            
            # check if round limit reached
            if self.state.game_state["round"] > self.state.game_state["num_rounds"]:
                # determine winner and return
                self._determine_winner()

    def _determine_winner(self):
        if self.state.game_state["total_payoff"][0] > self.state.game_state["total_payoff"][1]:
            winner_id = 0
            reason = self.m("outcome", "win", p0=self.state.game_state['total_payoff'][0], p1=self.state.game_state['total_payoff'][1], winner_id=winner_id)
            self.state.set_winner(player_id=winner_id, reason=reason)
        elif self.state.game_state["total_payoff"][1] > self.state.game_state["total_payoff"][0]:
            winner_id = 1
            reason = self.m("outcome", "win", p0=self.state.game_state['total_payoff'][0], p1=self.state.game_state['total_payoff'][1], winner_id=winner_id)
            self.state.set_winner(player_id=winner_id, reason=reason)
        else:
            reason = self.m("outcome", "draw", p0=self.state.game_state['total_payoff'][0], p1=self.state.game_state['total_payoff'][1])
            self.state.set_draw(reason=reason)