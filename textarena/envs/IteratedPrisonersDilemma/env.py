import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.IteratedPrisonersDilemma.renderer import create_board_str


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedPrisonersDilemmaEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    broadcast_actions = False  # raw action echoed only to its author

    cooperate_pattern = re.compile(r"^Cooperate$", re.IGNORECASE)
    defect_pattern    = re.compile(r"^Defect$",    re.IGNORECASE)

    num_rounds = ta.Param(5, "The number of rounds.", min=1, check=_is_renderable, rule="a positive integer")
    communication_turns = ta.Param(
        3, "The conversation turns before each decision, each one message per player; 0 skips conversation.",
        min=0, check=_is_renderable, rule="a non-negative integer",
    )
    cooperate_reward = ta.Param(3, "The payoff to each player when both cooperate.", check=_is_renderable, rule="an integer")
    defect_reward = ta.Param(5, "The payoff to a defector whose opponent cooperates.", check=_is_renderable, rule="an integer")
    sucker_reward = ta.Param(0, "The payoff to a cooperator whose opponent defects.", check=_is_renderable, rule="an integer")
    mutual_defect_reward = ta.Param(1, "The payoff to each player when both defect.", check=_is_renderable, rule="an integer")

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 1, "num_rounds": self.num_rounds,
            "phase": "decision" if self.communication_turns == 0 else "conversation",
            "conversation_round": 0, "total_conversation_rounds": self.communication_turns,
            "decisions": {0: None, 1: None}, "scores": {0: 0, 1: 0}, "history": [],
        }

    def on_start(self):
        self._announce_round_start()

    def get_board_str(self) -> str:
        return create_board_str(self.game_state)

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        return (
            f"You are Player {player_id} in an Iterated Prisoner's Dilemma spanning "
            f"{game_state['num_rounds']} rounds.\n\n"
            f"Game Structure:\n"
            f"- Before each decision you have {game_state['total_conversation_rounds']} "
            f"turns to communicate freely.\n"
            f"- After that, both players simultaneously choose 'cooperate' or 'defect'.\n\n"
            f"Payoff Matrix (fixed each round):\n"
            f"- Both Cooperate ➜ each {self.cooperate_reward}\n"
            f"- Both Defect ➜ each {self.mutual_defect_reward}\n"
            f"- One Defects, one Cooperates ➜ Defector {self.defect_reward}, "
            f"Cooperator {self.sucker_reward}\n\n"
            f"Winning:\n"
            f"- Payoffs add up over all rounds. The player with the higher total after the last round wins; equal totals are a draw.\n\n"
            f"How to Play:\n"
            f"- During conversation: type any text you wish.\n"
            f"- During decision phase: reply with just 'cooperate' or 'defect' (case-insensitive).\n"
            "The payoff matrix will remain the same every round:\n"
            f"- Both Cooperate: {self.cooperate_reward}\n"
            f"- Both Defect: {self.mutual_defect_reward}\n"
            f"- If you Defect while the other Cooperates: {self.defect_reward}\n"
            f"- If you Cooperate while the other Defects: {self.sucker_reward}"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if (
            not isinstance(player_id, int)
            or isinstance(player_id, bool)
            or not 0 <= player_id < self.state.num_players
            or not self.state.is_player_alive(player_id)
            or player_id != self.current_player_id
        ):
            return self.invalid("Action submitted by an unauthorized player.")
        match self.game_state["phase"]:
            case "conversation":    return self._handle_conversation_phase(player_id, action)
            case "decision":        return self._handle_decision_phase(player_id, action)

    def _strip_role_tags(self, text: str) -> str:
        """Remove sender labels such as '[GAME]' so chat cannot impersonate other senders."""
        tags = [f"[{role}]" for role in self.state.role_mapping.values()]
        previous = None
        while previous != text:
            previous = text
            for tag in tags:
                text = text.replace(tag, "")
        return text

    def _handle_conversation_phase(self, player_id: int, action: str) -> None:
        self.message(1 - player_id, self._strip_role_tags(action).strip(), ta.ObservationType.PLAYER_ACTION, from_id=player_id)

        # advance the conversation counter after the *second* player's turn
        if player_id == 1:
            self.game_state["conversation_round"] += 1

            if self.game_state["conversation_round"] >= \
               self.game_state["total_conversation_rounds"]:
                # switch to decision phase
                self.game_state["phase"] = "decision"
                self._announce_decision_phase()
        return None

    def _announce_round_start(self) -> None:
        self.broadcast(f"--- Starting Round {self.game_state['round']} ---", ta.ObservationType.GAME_MESSAGE)
        if self.game_state["phase"] == "decision":
            self._announce_decision_phase()

    def _announce_decision_phase(self) -> None:
        self.broadcast(
            f"Conversation finished for round {self.game_state['round']}. "
            "Please reply with 'cooperate' or 'defect'.",
            ta.ObservationType.GAME_BOARD,
        )

    def _handle_decision_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if self.game_state["decisions"][player_id] is not None:
            return self.invalid("You have already submitted a decision for this round.")
        if self.cooperate_pattern.search(action):
            decision = "cooperate"
        elif self.defect_pattern.search(action):
            decision = "defect"
        else:
            return self.invalid("Decision must be either 'cooperate' or 'defect'.")
        self.game_state["decisions"][player_id] = decision

        # resolve only after both players decided
        if all(d is not None for d in self.game_state["decisions"].values()):
            self._resolve_round()

            if self.game_state["round"] >= self.game_state["num_rounds"]:
                self.game_state["phase"] = "complete"
                return self._determine_winner()

            # reset for next round
            self.game_state["round"] += 1
            phase = "decision" if self.game_state["total_conversation_rounds"] == 0 else "conversation"
            self.game_state.update({"phase": phase, "conversation_round": 0, "decisions": {0: None, 1: None}})
            self._announce_round_start()
        return None

    def _resolve_round(self):
        d0 = self.game_state["decisions"][0]
        d1 = self.game_state["decisions"][1]

        # payoff logic
        if d0 == d1 == "cooperate":                 r0 = r1 = self.cooperate_reward;                    outcome = "Both players cooperated."
        elif d0 == d1 == "defect":                  r0 = r1 = self.mutual_defect_reward;                outcome = "Both players defected."
        elif d0 == "cooperate" and d1 == "defect":  r0, r1 = self.sucker_reward, self.defect_reward;    outcome = "Player 0 cooperated, Player 1 defected."
        else:                                       r0, r1 = self.defect_reward, self.sucker_reward;    outcome = "Player 0 defected, Player 1 cooperated."

        # update cumulative scores
        self.game_state["scores"][0] += r0
        self.game_state["scores"][1] += r1
        self.game_state["history"].append({
            "round": self.game_state["round"],
            "decisions": self.game_state["decisions"].copy(),
            "payoffs": {0: r0, 1: r1},
        })

        # round summary
        self.broadcast(
            f"Round {self.game_state['round']} results:\n{outcome}\nPlayer 0 earned {r0} (total {self.game_state['scores'][0]}), Player 1 earned {r1} (total {self.game_state['scores'][1]}).",
            ta.ObservationType.GAME_MESSAGE,
        )

    def _determine_winner(self) -> ta.Outcome:
        s0 = self.game_state["scores"][0]
        s1 = self.game_state["scores"][1]

        if s0 == s1:
            return self.draw(reason=f"Draw! Both players scored {s0}.")
        winner = 0 if s0 > s1 else 1
        return self.winner(winner, reason=f"Player {winner} wins {max(s0, s1)} - {min(s0, s1)}.")
