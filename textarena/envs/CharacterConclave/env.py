import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.CharacterConclave.renderer import create_board_str


class CharacterConclaveEnv(ta.GameEnv):
    min_players = 3
    max_players = 15

    character_budget = ta.Param(
        1_000, "The total number of characters each player may use during the discussion.", min=1,
    )

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        return {
            "phase": "discussion",
            "budget_remaining": {p: self.character_budget for p in range(self.state.num_players)},
            "votes": {},
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a {self.state.num_players} player game of Character Conclave.\nEach of you has a limited character budget of {self.character_budget} characters.\n"
            f"Use them up across multiple turns by sending messages. Before each of your turns you are shown how many characters you have left; "
            f"a longer message is cut off at that limit.\n\nOnce all players have used their budgets, each will vote exactly once "
            f"for the player they found most impressive by replying with that player's ID (for example, '2' or 'player 2').\n"
            f"You cannot vote for yourself.\nThe player with the most votes wins.\n"
        )

    def render(self, player_id: int) -> Optional[str]:
        gs = self.game_state
        if self.state.done:
            return None
        if gs["phase"] == "discussion":
            return f"Your remaining character budget: {gs['budget_remaining'][player_id]} of {self.character_budget} characters."
        if gs["phase"] == "voting":
            candidates = ", ".join(f"Player {pid}" for pid in self.state.alive_players if pid != player_id)
            return f"Voting phase: reply with the ID of the player you found most impressive. You can vote for: {candidates}."
        return None

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Discussion messages are broadcast manually (possibly truncated to the budget);
        # votes are never echoed (the voter gets a private confirmation instead).
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["phase"] == "discussion":
            text = self.strip_role_tags(action).strip()
            if not text:
                return self.invalid("Discussion messages cannot be empty.")
            remaining = gs["budget_remaining"][player_id]
            message = text[:remaining]  # truncate to remaining budget
            if not message.strip():
                return self.invalid("The portion of your message within the remaining budget cannot be empty.")
            self.broadcast(message, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            if len(message) < len(text):
                self.message(
                    player_id,
                    f"Your message was {len(text)} characters long, but you only had {remaining} characters left, "
                    f"so only the first {remaining} characters were sent. Your character budget is now used up.",
                    ta.ObservationType.GAME_MESSAGE,
                )
            gs["budget_remaining"][player_id] -= len(message)
            next_pid = self._next_player_where(
                player_id,
                lambda pid: self.state.is_player_alive(pid) and gs["budget_remaining"][pid] > 0,
            )
            if next_pid is None:  # every budget is exhausted -> voting starts with the current player
                self._start_voting(player_id)
            else:
                self.set_next_player(next_pid)
            return None

        # voting phase
        if player_id in gs["votes"]:
            return self.invalid("You have already submitted your vote.")
        vote, reason = self._validate_player_vote(player_id, action)
        if vote is None:
            return self.invalid(reason)
        gs["votes"][player_id] = vote
        self.message(player_id, f"You have successfully voted for Player {vote}.", ta.ObservationType.GAME_MESSAGE)
        return self._rotate_voting_or_finish(player_id)

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Eliminated players score -1 and cannot receive votes, so votes already cast for them stop counting.
        self.eliminate(player_id)
        alive = self.state.alive_players
        if self.game_state["phase"] == "discussion":
            self.game_state["budget_remaining"][player_id] = 0
            if len(alive) == 1:
                return self.winner(alive[0], reason=f"Player {player_id} was eliminated for repeated empty messages.")
            self.broadcast(
                f"Player {player_id} was eliminated for repeated empty messages and can no longer receive votes.",
                ta.ObservationType.GAME_ADMIN,
            )
            next_pid = self._next_player_where(
                player_id,
                lambda pid: self.state.is_player_alive(pid) and self.game_state["budget_remaining"][pid] > 0,
            )
            if next_pid is None:
                self._start_voting(self.state.next_alive_player(after=player_id))
            else:
                self.set_next_player(next_pid)
            return None

        self.game_state["votes"][player_id] = -1
        if len(alive) == 1:  # nobody is left for the survivor to vote for
            return self.winner(
                alive[0],
                reason=f"Player {player_id} was eliminated for repeated invalid votes, leaving Player {alive[0]} as the only remaining player.",
            )
        self.broadcast(
            f"Player {player_id} was eliminated for repeated invalid votes. "
            "Their vote is discarded, and votes cast for them do not count.",
            ta.ObservationType.GAME_ADMIN,
        )
        next_pid = self._next_player_where(
            player_id,
            lambda pid: self.state.is_player_alive(pid) and pid not in self.game_state["votes"],
        )
        if next_pid is None:
            return self._final_outcome()
        self.set_next_player(next_pid)
        return None

    def _start_voting(self, first_voter: int) -> None:
        self.game_state["phase"] = "voting"
        self.broadcast(
            "The discussion phase has concluded. Please now vote for a player by replying with 'player x' or 'x'.",
            ta.ObservationType.GAME_MESSAGE,
        )
        self.set_next_player(first_voter)

    def _next_player_where(self, player_id: int, can_take_turn) -> Optional[int]:
        """The next player (cyclically after `player_id`, ending with `player_id` itself) satisfying the predicate."""
        for offset in range(1, self.state.num_players + 1):
            pid = (player_id + offset) % self.state.num_players
            if can_take_turn(pid):
                return pid
        return None

    def _rotate_voting_or_finish(self, player_id: int) -> Optional[ta.Outcome]:
        next_pid = self._next_player_where(
            player_id,
            lambda pid: self.state.is_player_alive(pid) and pid not in self.game_state["votes"],
        )
        if next_pid is None:
            return self._final_outcome()
        self.set_next_player(next_pid)
        return None

    def _validate_player_vote(self, player_id: int, action: str) -> Tuple[Optional[int], Optional[str]]:
        match = re.search(r"^\s*(?:player\s+)?(\d+)\s*$", action, re.IGNORECASE)
        if not match: return None, "Invalid voting format. Please submit your vote as 'x' or 'player x'."
        try: target_pid = int(match.group(1))
        except ValueError: return None, "Could not parse the player ID from your vote."
        if target_pid < 0 or target_pid >= self.state.num_players: return None, f"Invalid vote. Player {target_pid} does not exist."
        if target_pid == player_id: return None, "You cannot vote for yourself!"
        if not self.state.is_player_alive(target_pid): return None, f"Invalid vote. Player {target_pid} has been eliminated."
        return target_pid, None

    def _final_outcome(self) -> ta.Outcome:
        vote_counts: Dict[int, int] = {}
        for voting_pid, target_pid in self.game_state["votes"].items():
            if target_pid not in self.state.eliminated and target_pid != -1:  # eliminated players can't be voted for
                vote_counts[target_pid] = vote_counts.get(target_pid, 0) + 1
        valid_players = [pid for pid in range(self.state.num_players) if pid not in self.state.eliminated]
        score_groups = []
        for pid in sorted(valid_players, key=lambda p: (vote_counts.get(p, 0), p)):
            if not score_groups or vote_counts.get(pid, 0) != vote_counts.get(score_groups[-1][0], 0):
                score_groups.append([pid])
            else:
                score_groups[-1].append(pid)

        reward_dict: Dict[int, float] = {}
        if len(score_groups) == 1:
            reward = 1.0 if len(valid_players) == 1 and self.state.eliminated else 0.0
            reward_dict.update({pid: reward for pid in score_groups[0]})
        else:
            for idx, group in enumerate(score_groups):
                reward = -1.0 + 2.0 * idx / (len(score_groups) - 1)
                reward_dict.update({pid: reward for pid in group})
        for pid in self.state.eliminated: reward_dict[pid] = -1.0
        self.game_state["phase"] = "finished"
        self.game_state["final_vote_counts"] = {pid: vote_counts.get(pid, 0) for pid in range(self.state.num_players)}
        self.broadcast(
            "Final vote count: " + ", ".join(
                f"P{pid}={self.game_state['final_vote_counts'][pid]}"
                for pid in range(self.state.num_players)
            ),
            ta.ObservationType.GAME_MESSAGE,
        )
        winners = [pid for pid, reward in reward_dict.items() if reward == 1.0]
        reason = (
            f"Player(s) {winners} win(s) with the most votes."
            if winners
            else "Voting ended in a complete tie."
        )
        return self.outcome(reward_dict, reason=reason)
