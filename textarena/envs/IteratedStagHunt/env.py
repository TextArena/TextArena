import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.IteratedStagHunt.renderer import create_board_str


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class IteratedStagHuntEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    broadcast_actions = False  # raw action echoed only to its author

    def __init__(self, num_rounds: int=5, conversation_rounds: int=3, mutual_stag_reward: int=10, single_hare_reward: int=8, single_stag_reward: int=1, mutual_hare_reward: int=5, randomize_payoff: bool=False):
        if (
            not isinstance(num_rounds, int)
            or isinstance(num_rounds, bool)
            or num_rounds <= 0
            or not _is_renderable(num_rounds)
        ):
            raise ValueError("num_rounds must be a positive integer")
        if (
            not isinstance(conversation_rounds, int)
            or isinstance(conversation_rounds, bool)
            or conversation_rounds < 0
            or not _is_renderable(conversation_rounds)
        ):
            raise ValueError("conversation_rounds must be a non-negative integer")
        rewards = (mutual_stag_reward, single_hare_reward, single_stag_reward, mutual_hare_reward)
        if any(
            not isinstance(reward, int)
            or isinstance(reward, bool)
            or not _is_renderable(reward)
            for reward in rewards
        ):
            raise ValueError("all rewards must be integers")
        if not isinstance(randomize_payoff, bool):
            raise ValueError("randomize_payoff must be a boolean")
        if randomize_payoff and not (
            single_stag_reward < mutual_hare_reward <= single_hare_reward < mutual_stag_reward
        ):
            raise ValueError(
                "randomized payoff bounds must satisfy "
                "single_stag < mutual_hare <= single_hare < mutual_stag"
            )

        self.num_rounds = num_rounds
        self.conversation_rounds = conversation_rounds

        # payoffs
        self.mutual_stag_reward = mutual_stag_reward
        self.single_hare_reward = single_hare_reward
        self.single_stag_reward = single_stag_reward
        self.mutual_hare_reward = mutual_hare_reward
        self.randomize_payoff = randomize_payoff

        # Action pattern (bare token, tolerating optional stray brackets)
        self.stag_pattern = re.compile(r"^\s*\[?\s*Stag\s*\]?\s*$", re.IGNORECASE)
        self.hare_pattern = re.compile(r"^\s*\[?\s*Hare\s*\]?\s*$", re.IGNORECASE)

    def setup(self) -> Dict[str, Any]:
        return {
            "round": 1, "num_rounds": self.num_rounds,
            "phase": "decision" if self.conversation_rounds == 0 else "conversation",
            "conversation_round": 0, "total_conversation_rounds": self.conversation_rounds,
            "decisions": {0: None, 1: None}, "total_payoff": {0: 0, 1: 0},
            "payoffs": {}, "history": [],
        }

    def on_start(self):
        self._create_round_payoff_matrix()
        if self.game_state["phase"] == "decision":
            self._announce_decision_phase()

    def get_board_str(self) -> str:
        return create_board_str(self.game_state)

    def prompt(self, player_id: int) -> str:
        """Generate the initial prompt for a player."""
        game_state = self.game_state
        return (
            f"You are Player {player_id} in an {game_state['num_rounds']} round game of Iterated Stag Hunt.\n\n"
            f"Game Structure:\n"
            f"- The game consists of {self.num_rounds} decision rounds\n"
            f"- Before each decision, you have {game_state['total_conversation_rounds']} turns to communicate\n"
            f"- After communication, both players simultaneously choose to hunt a Stag or Hare\n\n"
            f"Rewards:\n"
            f"- The rewards associated with hunting stags and hares may differ between rounds\n"
            f"- The rewards are presented at the start of each round\n\n"
            f"How to Play:\n"
            f"- During communication: Simply type your message\n"
            f"- During decision phase: Reply with just 'stag' or 'hare'\n"
        )

    def _create_round_payoff_matrix(self) -> None:
        payoffs = self.game_state["payoffs"]
        if not self.randomize_payoff:
            payoffs["mutual_stag"] = self.mutual_stag_reward
            payoffs["single_stag"] = self.single_stag_reward
            payoffs["single_hare"] = self.single_hare_reward
            payoffs["mutual_hare"] = self.mutual_hare_reward
        else:
            payoffs["single_stag"] = self.single_stag_reward
            payoffs["mutual_hare"] = self.rng.randint(payoffs["single_stag"] + 1, self.mutual_hare_reward)
            payoffs["single_hare"] = self.rng.randint(payoffs["mutual_hare"], self.single_hare_reward)
            payoffs["mutual_stag"] = self.rng.randint(payoffs["single_hare"] + 1, self.mutual_stag_reward)

        cadence = (
            f"You can freely communicate with your opponent for "
            f"{self.game_state['total_conversation_rounds']} rounds before making a decision."
            if self.game_state["total_conversation_rounds"]
            else "There is no communication phase this round; make your decision now."
        )
        message = (
            f"Starting Round {self.game_state['round']} with payoff matrix:\n"
            f"- Both hunt a Stag: Both get {payoffs['mutual_stag']} points\n"
            f"- Both hunt a Hare: Both get {payoffs['mutual_hare']} points\n"
            f"- One hunts a Hare, One hunts a Stag: The hunter of the Hare gets {payoffs['single_hare']} points, the hunter of the Stag gets {payoffs['single_stag']} points\n"
            f"{cadence}"
        )
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    def _announce_decision_phase(self) -> None:
        self.broadcast(
            f"The decision phase for round {self.game_state['round']} has started. "
            "Please reply with either 'stag' or 'hare'.",
            ta.ObservationType.GAME_BOARD,
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
        # check what phase we are in
        match self.game_state["phase"]:
            case "conversation":    return self._handle_conversation_phase(player_id, action)
            case "decision":        return self._handle_decision_phase(player_id, action)

    def _handle_conversation_phase(self, player_id: int, action: str) -> None:
        # relay player action to opponent
        self.message(1 - player_id, action.strip(), ta.ObservationType.PLAYER_ACTION, from_id=player_id)

        # only increment conversation round on player 1
        if player_id == 1:
            self.game_state["conversation_round"] += 1

            # check if we have completed all conversation rounds
            if self.game_state["conversation_round"] >= self.game_state["total_conversation_rounds"]:
                self.game_state["phase"] = "decision"  # rotate phase
                self._announce_decision_phase()
        return None

    def _handle_decision_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["decisions"][player_id] is not None:
            return self.invalid("You have already submitted a decision for this round.")
        if self.stag_pattern.search(action):
            decision = "stag"
        elif self.hare_pattern.search(action):
            decision = "hare"
        else:
            return self.invalid("Decision must be either 'stag' or 'hare'.")
        gs["decisions"][player_id] = decision

        # check if we have both decisions
        if all(decision is not None for decision in gs["decisions"].values()):
            payoffs = gs["payoffs"]
            # determine pay-off & send message
            round_payoffs = [None, None]
            if gs["decisions"][0] == gs["decisions"][1]:  # matching decision
                round_payoffs[0] = round_payoffs[1] = (payoffs["mutual_stag"] if gs["decisions"][0] == "stag" else payoffs["mutual_hare"])
            else:  # differing decisions
                round_payoffs[0] = payoffs["single_stag"] if gs["decisions"][0] == "stag" else payoffs["single_hare"]
                round_payoffs[1] = payoffs["single_stag"] if gs["decisions"][1] == "stag" else payoffs["single_hare"]

            message = f"Round {gs['round']} complete. Results:"
            for pid in [0, 1]:
                gs['total_payoff'][pid] += round_payoffs[pid]
                message += f"\n\tPlayer {pid} picked '{gs['decisions'][pid]}' (payoff: {round_payoffs[pid]}; total: {gs['total_payoff'][pid]})"
            gs["history"].append({
                "round": gs["round"],
                "decisions": gs["decisions"].copy(),
                "payoffs": {0: round_payoffs[0], 1: round_payoffs[1]},
                "matrix": payoffs.copy(),
            })
            self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

            # check if round limit reached
            if gs["round"] >= gs["num_rounds"]:
                gs["phase"] = "complete"
                return self._determine_winner()

            # start next round
            gs["round"] += 1
            gs["phase"] = "decision" if gs["total_conversation_rounds"] == 0 else "conversation"
            gs["conversation_round"] = 0
            gs["decisions"] = {0: None, 1: None}
            self._create_round_payoff_matrix()
            if gs["phase"] == "decision":
                self._announce_decision_phase()
        return None

    def _determine_winner(self) -> ta.Outcome:
        gs = self.game_state
        if gs["total_payoff"][0] > gs["total_payoff"][1]:
            winner_id = 0
            return self.winner(winner_id, reason=f"Final scores: Player 0: {gs['total_payoff'][0]}, Player 1: {gs['total_payoff'][1]}\nPlayer {winner_id} won!")
        elif gs["total_payoff"][1] > gs["total_payoff"][0]:
            winner_id = 1
            return self.winner(winner_id, reason=f"Final scores: Player 0: {gs['total_payoff'][0]}, Player 1: {gs['total_payoff'][1]}\nPlayer {winner_id} won!")
        else:
            return self.draw(reason=f"Final scores: Player 0: {gs['total_payoff'][0]}, Player 1: {gs['total_payoff'][1]}\nIt's a Tie!")
