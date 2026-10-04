import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.WinAsMuchAsYouCan.renderer import get_board_str


class WinAsMuchAsYouCanEnv(ta.GameEnv):
    """
    Win as Much as You Can environment.

    A 4-player game where players choose X or Y in 10 rounds to maximize points.
    Features communication phases in rounds 5, 8, and 10 with different scoring multipliers.

    Key mechanics:
    - 4 players (fixed)
    - 10 scoring rounds with specific communication phases
    - Point scoring based on X/Y distribution
    - Communication phases with public/private messaging
    - Scoring multipliers: 1x (rounds 1-4,6-7,9), 3x (round 5), 5x (round 8), 10x (round 10)
    """

    min_players = 4
    max_players = 4

    def __init__(self, error_allowance: int = 3):
        """
        Initialize the Win as Much as You Can environment.

        Args:
            error_allowance: Number of invalid moves allowed per player
        """
        if (
            not isinstance(error_allowance, int)
            or isinstance(error_allowance, bool)
            or error_allowance < 0
        ):
            raise ValueError("error_allowance must be a non-negative integer")
        self.error_allowance = error_allowance

        # Regex patterns for parsing actions
        self.broadcast_pattern = re.compile(r"^\s*Broadcast\s*:\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL)
        self.whisper_pattern = re.compile(
            r"^\s*Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)\s*:\s*(.+?)\s*$",
            re.IGNORECASE | re.DOTALL,
        )
        self.legacy_broadcast_pattern = re.compile(r"^\s*\[Broadcast\]\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL)
        self.legacy_whisper_pattern = re.compile(
            r"^\s*\[Whisper\s+to\s+(\d+)\]\s*(.+?)\s*$",
            re.IGNORECASE | re.DOTALL,
        )
        self.pass_pattern = re.compile(r"^\s*\[?\s*Pass\s*\]?\s*$", re.IGNORECASE)
        self.choose_x_pattern = re.compile(r"^\s*\[?\s*Choose\s+X\s*\]?\s*$", re.IGNORECASE)
        self.choose_y_pattern = re.compile(r"^\s*\[?\s*Choose\s+Y\s*\]?\s*$", re.IGNORECASE)

    def reset(self, num_players: int, seed: Optional[int] = None):
        if num_players != 4:
            raise ValueError("Win as Much as You Can requires exactly 4 players")
        super().reset(num_players=num_players, seed=seed)

    def setup(self) -> Dict[str, Any]:
        return {
            "current_round": 1,
            "current_phase": "act",  # rounds 1-4 have no talk phase
            "player_choices": {},
            "player_scores": {0: 0, 1: 0, 2: 0, 3: 0},
            "round_history": [],
            "talk_round": 0,
            "max_talk_rounds": 40,
            "talk_actions_by_player": {0: 0, 1: 0, 2: 0, 3: 0},
            "players_passed": set(),
            "talk_messages": [],
            "round_multipliers": {
                1: 1, 2: 1, 3: 1, 4: 1,
                5: 3,
                6: 1, 7: 1,
                8: 5,
                9: 1,
                10: 10
            },
            "communication_rounds": {5, 8, 10},
        }

    def prompt(self, player_id: int) -> str:
        return f"""You are Player {player_id} in Win as Much as You Can.

OBJECTIVE:
Earn the most points possible over 10 rounds by choosing X or Y strategically.

SCORING RUBRIC (per round):
- 1 X and 3 Y's: X wins 3 points, Y's lose 1 point each
- 2 X's and 2 Y's: X's win 2 points each, Y's lose 2 points each  
- 3 X's and 1 Y: X's win 1 point each, Y loses 3 points
- 4 X's: All X's lose 1 point each
- 4 Y's: All Y's win 1 point each

ROUND STRUCTURE:
- Rounds 1-4, 6-7, 9: Act phase only (1x points)
- Round 5: Talk phase -> Act phase (3x points)
- Round 8: Talk phase -> Act phase (5x points)  
- Round 10: Talk phase -> Act phase (10x points)

TALK PHASE RULES:
- Maximum 40 conversation rounds (10 per player)
- Public messages: 'Broadcast: your message' (everyone sees sender and content)
- Private messages: 'Whisper X: your message' (only sender and receiver know content, others see "A private message was sent")
- End participation: reply with 'Pass'
- Phase ends when max rounds reached OR all players pass

ACT PHASE RULES:
- Choose your action: 'Choose X' or 'Choose Y'
- All players choose simultaneously
- Round scored when all choices collected
"""

    def render(self, player_id: int) -> str:
        return get_board_str(self.state.game_state, player_id)

    def get_board_str(self) -> str:
        return get_board_str(self.state.game_state, self.state.current_player_id)

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Valid talk actions are routed explicitly below, and act choices must
        # remain secret until all four players have chosen.
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Players are never removed from play: the offender keeps their turn and
        # must still submit a valid action (matching the legacy behavior where
        # "elimination" had no effect on this game).
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if self.game_state["current_phase"] == "talk":
            return self._process_talk_phase(player_id, action)
        return self._process_act_phase(player_id, action)

    # ------------------------------------------------------------ talk phase
    def _process_talk_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if player_id in gs["players_passed"]:
            return self.invalid("You have already passed")

        broadcast_match = self._match_broadcast(action)
        whisper_match = self._match_whisper(action)
        pass_match = self.pass_pattern.search(action)

        if broadcast_match:
            message = broadcast_match.group(1).strip()
            if not message:
                return self.invalid("Broadcast message cannot be empty")
            self.broadcast(f"Player {player_id} (Broadcast): {message}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["talk_messages"].append({
                "round": gs["current_round"], "talk_round": gs["talk_round"],
                "from": player_id, "to": "all", "message": message, "type": "broadcast",
            })
        elif whisper_match:
            target_str = whisper_match.group(1)
            message = whisper_match.group(2).strip()
            try:
                target_id = int(target_str)
            except ValueError:
                return self.invalid(f"Invalid target player: {target_str}")
            if target_id < 0 or target_id >= 4:
                return self.invalid("Target player must be 0, 1, 2, or 3")
            if target_id == player_id:
                return self.invalid("Cannot whisper to yourself")
            if not message:
                return self.invalid("Whisper message cannot be empty")

            self.message(target_id, f"Player {player_id} (Private): {message}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.message(player_id, f"You sent private message to Player {target_id}: {message}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            for pid in range(4):
                if pid != player_id and pid != target_id:
                    self.message(pid, "A private message was sent between two players", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["talk_messages"].append({
                "round": gs["current_round"], "talk_round": gs["talk_round"],
                "from": player_id, "to": target_id, "message": message, "type": "whisper",
                "hidden": True,  # All private messages are anonymous
            })
        elif pass_match:
            gs["players_passed"].add(player_id)
            self.broadcast(f"Player {player_id} passed", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            return self.invalid("Reply with 'Broadcast: message', 'Whisper X: message', or 'Pass'")

        # valid talk action: advance the talk round, maybe end the phase
        gs["talk_round"] += 1
        gs["talk_actions_by_player"][player_id] += 1
        if (
            gs["talk_actions_by_player"][player_id] >= 10
            and player_id not in gs["players_passed"]
        ):
            gs["players_passed"].add(player_id)
            self.broadcast(
                f"Player {player_id} reached the 10-action talk limit and automatically passed",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
        if gs["talk_round"] >= gs["max_talk_rounds"] or len(gs["players_passed"]) >= 4:
            self._start_act_phase()
            return None
        next_talker = self._get_next_talk_player(player_id)
        if next_talker is not None:
            self.set_next_player(next_talker)
        return None

    def _match_broadcast(self, action: str):
        return self.broadcast_pattern.search(action) or self.legacy_broadcast_pattern.search(action)

    def _match_whisper(self, action: str):
        return self.whisper_pattern.search(action) or self.legacy_whisper_pattern.search(action)

    def _start_act_phase(self):
        gs = self.game_state
        gs["current_phase"] = "act"
        gs["player_choices"] = {}
        self.broadcast(f"Talk phase ended. Now choosing X or Y for Round {gs['current_round']}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.set_next_player(0)

    def _get_next_talk_player(self, current_player: int) -> Optional[int]:
        gs = self.game_state
        if gs["talk_round"] >= gs["max_talk_rounds"]:
            return None
        for i in range(1, 5):  # cycles back to the current player if everyone else passed
            next_player = (current_player + i) % 4
            if next_player not in gs["players_passed"]:
                return next_player
        return None

    # ------------------------------------------------------------- act phase
    def _process_act_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if player_id in gs["player_choices"]:
            return self.invalid("You have already made your choice this round")

        if self.choose_x_pattern.search(action):
            gs["player_choices"][player_id] = "X"
        elif self.choose_y_pattern.search(action):
            gs["player_choices"][player_id] = "Y"
        else:
            return self.invalid("Reply with 'Choose X' or 'Choose Y'")
        self.broadcast(f"Player {player_id} made their choice", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if len(gs["player_choices"]) >= 4:
            return self._finish_round()
        next_chooser = next(pid for pid in range(4) if pid not in gs["player_choices"])
        self.set_next_player(next_chooser)
        return None

    def _finish_round(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        self._score_round()
        if gs["current_round"] >= 10:
            return self._end_game()

        gs["current_round"] += 1
        if gs["current_round"] in gs["communication_rounds"]:
            gs["current_phase"] = "talk"
            gs["talk_round"] = 0
            gs["talk_actions_by_player"] = {0: 0, 1: 0, 2: 0, 3: 0}
            gs["players_passed"] = set()
            gs["player_choices"] = {}
            self.broadcast(f"Round {gs['current_round']} - Talk phase begins", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            gs["current_phase"] = "act"
            gs["player_choices"] = {}
            self.broadcast(f"Round {gs['current_round']} - Choose X or Y", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.set_next_player(0)
        return None

    def _score_round(self):
        gs = self.game_state
        choices = gs["player_choices"]
        current_round = gs["current_round"]
        multiplier = gs["round_multipliers"][current_round]

        x_count = sum(1 for choice in choices.values() if choice == "X")
        y_count = 4 - x_count

        if x_count == 1 and y_count == 3:
            base_points = {"X": 3, "Y": -1}
        elif x_count == 2 and y_count == 2:
            base_points = {"X": 2, "Y": -2}
        elif x_count == 3 and y_count == 1:
            base_points = {"X": 1, "Y": -3}
        elif x_count == 4:
            base_points = {"X": -1, "Y": 0}
        elif y_count == 4:
            base_points = {"X": 0, "Y": 1}
        else:
            base_points = {"X": 0, "Y": 0}

        round_results = {}
        for player_id, choice in choices.items():
            points_earned = base_points[choice] * multiplier
            gs["player_scores"][player_id] += points_earned
            round_results[player_id] = {"choice": choice, "points": points_earned}

        gs["round_history"].append({
            "round": current_round,
            "choices": choices.copy(),
            "x_count": x_count,
            "y_count": y_count,
            "base_points": base_points.copy(),
            "multiplier": multiplier,
            "results": round_results.copy(),
        })

        choices_str = ", ".join([f"Player {pid}: {choice}" for pid, choice in sorted(choices.items())])
        self.broadcast(f"Round {current_round} Results: {choices_str} ({x_count} X's, {y_count} Y's)", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        for player_id, result in round_results.items():
            self.broadcast(f"Player {player_id}: {result['points']:+d} points (Total: {gs['player_scores'][player_id]})", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _end_game(self) -> ta.Outcome:
        gs = self.game_state
        final_scores = gs["player_scores"]
        max_score = max(final_scores.values())
        winners = [pid for pid, score in final_scores.items() if score == max_score]

        self.broadcast("GAME OVER - Final Scores:", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        for player_id in range(4):
            self.broadcast(f"Player {player_id}: {final_scores[player_id]} points", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if len(winners) == 1:
            reason = f"Player {winners[0]} wins with {max_score} points!"
        else:
            reason = f"Tie between players {winners} with {max_score} points each!"

        # Highest score wins even when every score is non-positive.
        rewards = {pid: (1 if pid in winners else -1) for pid in range(4)}
        return self.outcome(rewards, reason=reason)
