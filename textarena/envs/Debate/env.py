import copy
import importlib.resources
import inspect
import json
import math
import os
from numbers import Real
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.Debate.renderer import create_board_str

class DebateEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    snapshot_excluded_attributes = ("jury",)
    max_argument_chars = 10_000
    max_jury_size = 100

    max_turns = ta.Param(
        4, "The number of arguments in the whole debate. The players alternate, so each gets half of them.",
        check=lambda turns: turns >= 2 and turns % 2 == 0, rule="an even integer of at least 2",
    )
    jury_size = ta.Param(5, "The number of jurors.", min=1, max=max_jury_size)
    jury_class = ta.Param(
        None, "The class or factory called with `options` and `jury_size` (and the env's seeded `rng` if it accepts "
              "one). The object it returns must provide `evaluate(context)` returning "
              "`{\"Affirmative\": votes, \"Negative\": votes}`. None uses `OpenRouterJury`.",
        type=object, check=callable, rule="a callable",
    )
    topics_path = ta.Param(
        None, "A JSON file of the form `{\"topics\": [\"...\", ...]}` with unique, non-empty topics. None uses the "
              "bundled `topics.json`.", type=str,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.jury_class is None:
            from textarena.utils import OpenRouterJury
            self._jury_class = OpenRouterJury
        else:
            self._jury_class = self.jury_class
        self._load_topics(self.topics_path)
        self.jury = None

    def get_board_str(self): return create_board_str(game_state=self.game_state)
    def _load_topics(self, topics_path: Optional[str]):
        try:
            if topics_path is not None:
                if not os.path.exists(topics_path):
                    raise FileNotFoundError(f"Topics data file not found at: {topics_path}")
                with open(topics_path, "r", encoding="utf-8") as file:
                    payload = json.load(file)
            else:
                with importlib.resources.files("textarena.envs.Debate").joinpath(
                    "topics.json"
                ).open("r", encoding="utf-8") as file:
                    payload = json.load(file)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load topics data: {exc}") from exc
        self.topics = payload.get("topics") if isinstance(payload, dict) else None
        if (
            not isinstance(self.topics, list)
            or not self.topics
            or any(not isinstance(topic, str) or not topic.strip() for topic in self.topics)
            or len({topic.strip().casefold() for topic in self.topics}) != len(self.topics)
        ):
            raise ValueError("Topics data must contain a non-empty list of unique, non-empty strings.")

    def setup(self) -> Dict[str, Any]:
        self.jury = None
        affirmative_player_id = self.rng.choice([0, 1])
        game_state = {
            "arguments": {0: [], 1: []}, "topic": self.rng.choice(self.topics),
            "sides": {affirmative_player_id: "Affirmative", 1-affirmative_player_id: "Negative"},
            "votes": {"pre-debate": {"Affirmative": 0, "Negative": 0}, "post-debate": {"Affirmative": 0, "Negative": 0}},
            "pre_vote_recorded": False,
        }
        return game_state

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        return (
            f"You are Player {player_id} in the Debate game.\nTopic: {game_state['topic']}\nYour position: {game_state['sides'][player_id]}\n"
            f"You will have {self.max_turns} total turns (shared between both players) to present your arguments. "
            f"Player 0 speaks first and the players alternate, so each of you gets {self.max_turns // 2} turns. "
            f"On your turn, type your argument (at most {self.max_argument_chars} characters).\n"
            f"Scoring: a jury of {self.jury_size} AI jurors votes Affirmative or Negative on the topic before the debate "
            "and again after reading the full transcript. The side whose share of the vote grows more wins; equal gains "
            "are a draw.\n"
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Echo only after the argument (and any required jury call) succeeds.
        return None

    @staticmethod
    def _copy_resource(resource):
        try:
            return copy.deepcopy(resource), True
        except Exception:
            return None, False

    def _restore_jury_checkpoint(self, original, checkpoint, copied: bool):
        if copied:
            if (
                original is not None
                and checkpoint is not None
                and type(original) is type(checkpoint)
                and hasattr(original, "__dict__")
                and hasattr(checkpoint, "__dict__")
            ):
                original.__dict__.clear()
                original.__dict__.update(copy.deepcopy(checkpoint.__dict__))
                self.jury = original
            else:
                self.jury = checkpoint
        elif original is None:
            self.jury = None

    def snapshot(self) -> Dict[str, Any]:
        snapshot = super().snapshot()
        resource, copied = self._copy_resource(self.jury)
        snapshot["jury_resource"] = {"copied": copied, "value": resource}
        return snapshot

    def restore(self, snapshot: Dict[str, Any]):
        super().restore(snapshot)
        resource = snapshot.get("jury_resource", {})
        if resource.get("copied"):
            self.jury = copy.deepcopy(resource["value"])

    def _create_jury(self):
        jury_kwargs = {
            "jury_size": self.jury_size,
            "options": ["Affirmative", "Negative"],
        }
        try:
            parameters = inspect.signature(self._jury_class).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        if any(
            parameter.name == "rng" or parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        ):
            jury_kwargs["rng"] = self.rng
        return self._jury_class(**jury_kwargs)

    def _ask_jury(self, prompt: str) -> Dict[str, float]:
        if self.jury is None:
            self.jury = self._create_jury()
        return self.jury.evaluate(context=prompt)

    def _evaluate_debate(self, topic: str, debate_transcript: Optional[str]=None) -> Dict[str, float]:
        rng_state = self.rng.getstate()
        original_jury = self.jury
        checkpoint, copied = self._copy_resource(original_jury)
        try:
            prompt = f"Debate Topic: {topic}\n"
            if debate_transcript: prompt += f"Debate Transcript:\n{debate_transcript}\nPlease vote for either 'Affirmative' or 'Negative'."
            else: prompt += "No debate has occurred yet. Please vote based solely on the topic.\nVote for either 'Affirmative' or 'Negative'."
            votes = self.ask(self._ask_jury, prompt)
            expected = {"Affirmative", "Negative"}
            if not isinstance(votes, dict) or set(votes) != expected:
                raise ValueError("jury result must contain exactly Affirmative and Negative.")
            if any(
                isinstance(vote, bool)
                or not isinstance(vote, Real)
                or not math.isfinite(float(vote))
                or vote < 0
                for vote in votes.values()
            ):
                raise ValueError("jury votes must be finite non-negative numbers.")
            vote_total = sum(float(vote) for vote in votes.values())
            if not math.isfinite(vote_total) or not 0 < vote_total <= self.jury_size:
                raise ValueError(
                    "jury vote total must be positive, finite, and no larger than jury_size."
                )
            return votes
        except Exception:
            self.rng.setstate(rng_state)
            self._restore_jury_checkpoint(original_jury, checkpoint, copied)
            raise

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        argument = self.strip_role_tags(action).strip() if isinstance(action, str) else ""
        if not argument:
            return self.invalid("An argument must contain non-whitespace text.")
        if len(argument) > self.max_argument_chars:
            return self.invalid(f"Arguments are limited to {self.max_argument_chars} characters.")
        if not self.game_state["pre_vote_recorded"]:
            try:
                pre_votes = self._evaluate_debate(topic=self.game_state["topic"])
            except Exception:
                return self.retryable("The jury could not cast its pre-debate vote.")
            self.game_state["votes"]["pre-debate"] = pre_votes
            self.game_state["pre_vote_recorded"] = True

        proposed_arguments = {
            pid: list(arguments) for pid, arguments in self.game_state["arguments"].items()
        }
        proposed_arguments[player_id].append(argument)
        if self.state.turn >= self.max_turns - 1: # Check if the debate has ended
            try:
                winner_id, post_votes = self._determine_debate_winner(proposed_arguments)
            except Exception:
                return self.retryable("The jury could not cast its post-debate vote.")
            self.game_state["arguments"] = proposed_arguments
            self.game_state["votes"]["post-debate"] = post_votes
            self.broadcast(argument, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
            if winner_id is None:
                return self.draw(reason="The jury's opinion did not favor either side more.")
            return self.winner(winner_id, reason=f"Player {winner_id} wins by gaining more support.")
        self.game_state["arguments"] = proposed_arguments
        self.broadcast(argument, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        return None

    def _determine_debate_winner(self, arguments: Dict[int, list]):
        transcript_lines = []
        max_rounds = max(len(arguments[0]), len(arguments[1]))
        for i in range(max_rounds):
            if i < len(arguments[0]): transcript_lines.append(f"Player 0 ({self.game_state['sides'][0]}): {arguments[0][i]}")
            if i < len(arguments[1]): transcript_lines.append(f"Player 1 ({self.game_state['sides'][1]}): {arguments[1][i]}")
        debate_transcript = "\n".join(transcript_lines)

        # Conduct post-debate voting
        post_votes = self._evaluate_debate(topic=self.game_state["topic"], debate_transcript=debate_transcript)

        # Calculate vote gains
        pre_votes = self.game_state["votes"]["pre-debate"]
        gain_aff = post_votes["Affirmative"] - pre_votes["Affirmative"]
        gain_neg = post_votes["Negative"] - pre_votes["Negative"]

        # Determine winner or tie
        if gain_aff > gain_neg:     winner_side = "Affirmative"
        elif gain_neg > gain_aff:   winner_side = "Negative"
        else: return None, post_votes  # tie

        # Map winning side to player ID
        for pid, side in self.game_state["sides"].items():
            if side == winner_side: return pid, post_votes
        return None, post_votes
