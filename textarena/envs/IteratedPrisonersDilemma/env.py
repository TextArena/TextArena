import re
from typing import Dict, Any, Optional, Tuple

import textarena as ta
# from textarena.envs.IteratedPrisonersDilemma.renderer import create_board_str  # add when you have a renderer


class IteratedPrisonersDilemmaEnv(ta.Env):
    def __init__(self, num_rounds: int=5, communication_turns: int=3, cooperate_reward: int=3, defect_reward: int=5, sucker_reward: int=0, mutual_defect_reward: int = 1):
        # game/round structure
        self.num_rounds = num_rounds
        self.conversation_rounds = communication_turns

        # payoff matrix (constant across rounds)
        self.cooperate_reward = cooperate_reward
        self.defect_reward = defect_reward
        self.sucker_reward = sucker_reward
        self.mutual_defect_reward = mutual_defect_reward

        # action regex
        self.cooperate_pattern = re.compile(r"\[Cooperate\]", re.IGNORECASE)
        self.defect_pattern    = re.compile(r"\[Defect\]",    re.IGNORECASE)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {
            "round": 1, "num_rounds": self.num_rounds, "phase": "conversation", "conversation_round": 0,
            "total_conversation_rounds": self.conversation_rounds, "decisions": {0: None, 1: None}, "scores": {0: 0, 1: 0},
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(message=self.m("phases", "starting_round", round=self.state.game_state['round']), observation_type=ta.ObservationType.GAME_MESSAGE)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, num_rounds=game_state["num_rounds"], total_conversation_rounds=game_state["total_conversation_rounds"], cooperate_reward=self.cooperate_reward, mutual_defect_reward=self.mutual_defect_reward, defect_reward=self.defect_reward, sucker_reward=self.sucker_reward)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(to_id=self.state.current_player_id, from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match self.state.game_state["phase"]:
            case "conversation":    self._handle_conversation_phase(action)
            case "decision":        self._handle_decision_phase(action)
        return self.state.step()

    def _handle_conversation_phase(self, action: str):
        self.state.add_observation(to_id=1-self.state.current_player_id, from_id=self.state.current_player_id, message=action.strip(), observation_type=ta.ObservationType.PLAYER_ACTION)

        # advance the conversation counter after the *second* player's turn
        if self.state.current_player_id == 1:
            self.state.game_state["conversation_round"] += 1

            if self.state.game_state["conversation_round"] >= \
               self.state.game_state["total_conversation_rounds"]:
                # switch to decision phase
                self.state.game_state["phase"] = "decision"
                self.state.add_observation(message=self.m("phases", "conversation_finished", round=self.state.game_state['round']), observation_type=ta.ObservationType.GAME_BOARD)

    def _handle_decision_phase(self, action: str):
        decision = "defect" if self.defect_pattern.search(action) else "cooperate"
        self.state.game_state["decisions"][self.state.current_player_id] = decision

        # resolve only after both players decided
        if all(d is not None for d in self.state.game_state["decisions"].values()):
            self._resolve_round()

            # advance to next round or finish
            self.state.game_state["round"] += 1
            if self.state.game_state["round"] > self.state.game_state["num_rounds"]:
                self._determine_winner()
            else:
                # reset for next round
                self.state.game_state.update({"phase": "conversation", "conversation_round": 0, "decisions": {0: None, 1: None}})
                self.state.add_observation(message=self.m("phases", "starting_round", round=self.state.game_state['round']), observation_type=ta.ObservationType.GAME_MESSAGE)

    def _resolve_round(self):
        d0 = self.state.game_state["decisions"][0]
        d1 = self.state.game_state["decisions"][1]

        # payoff logic
        if d0 == d1 == "cooperate":                 r0 = r1 = self.cooperate_reward;                    outcome = self.m("outcome", "round_both_cooperate")
        elif d0 == d1 == "defect":                  r0 = r1 = self.mutual_defect_reward;                outcome = self.m("outcome", "round_both_defect")
        elif d0 == "cooperate" and d1 == "defect":  r0, r1 = self.sucker_reward, self.defect_reward;    outcome = self.m("outcome", "round_p0_cooperates_p1_defects")
        else:                                       r0, r1 = self.defect_reward, self.sucker_reward;    outcome = self.m("outcome", "round_p0_defects_p1_cooperates")

        # update cumulative scores
        self.state.game_state["scores"][0] += r0
        self.state.game_state["scores"][1] += r1

        # round summary
        self.state.add_observation(
            message=self.m("phases", "round_summary", round=self.state.game_state['round'], outcome=outcome, r0=r0, score_0=self.state.game_state['scores'][0], r1=r1, score_1=self.state.game_state['scores'][1]),
            observation_type=ta.ObservationType.GAME_MESSAGE,
        )

    def _determine_winner(self):
        s0 = self.state.game_state["scores"][0]
        s1 = self.state.game_state["scores"][1]

        if s0 == s1:
            self.state.set_draw(reason=self.m("outcome", "draw", s0=s0))
        else:
            winner = 0 if s0 > s1 else 1
            self.state.set_winner(player_id=winner, reason=self.m("outcome", "winner", winner=winner, win_score=max(s0, s1), lose_score=min(s0, s1)))
