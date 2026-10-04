import copy
import importlib.resources
import json
import os
import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta
from textarena.envs.TwentyQuestions.renderer import create_board_str


class TwentyQuestionsEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    snapshot_excluded_attributes = ("gamemaster",)
    max_action_chars = 4_000
    max_gamemaster_response_chars = 256
    _GUESS_RE = re.compile(r"^\s*guess(?:\s+|:\s*)(?P<guess>.+?)\s*$", re.IGNORECASE)
    _LEGACY_GUESS_RE = re.compile(r"^\s*\[(?P<guess>[^\[\]]+)\]\s*$")
    _EMPTY_GUESS_RE = re.compile(r"^\s*(?:guess\s*:?\s*|\[\s*\])$", re.IGNORECASE)
    _GAMEMASTER_RESPONSE_RE = re.compile(
        r"""^\s*(?:answer\s*:\s*)?["'“”]?(?P<answer>yes|no|i\s+don['’]t\s+know)["'“”]?[.!]?\s*$""",
        re.IGNORECASE,
    )

    def __init__(
        self,
        hardcore: bool = False,
        max_turns: int = 21,
        gamemaster: Optional[Any] = None,
        words_path: Optional[str] = None,
    ):
        """
        Args:
            hardcore: Whether to use more challenging words
            max_turns: Maximum number of turns allowed in the game
        """
        if not isinstance(hardcore, bool):
            raise TypeError("hardcore must be a boolean.")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 2:
            raise ValueError("max_turns must be an integer of at least 2 (questions plus a final guess).")
        if gamemaster is not None and not callable(gamemaster):
            raise TypeError("gamemaster must be callable.")
        self.hardcore = hardcore
        self.max_turns = max_turns

        # The default network agent is created only when a question is asked. This
        # keeps construction/reset and locally-scored guesses usable offline.
        self.gamemaster = gamemaster
        self.gamemaster_options = ["Yes", "No", "I don't know"]

        # Load the word list
        self.word_list = self._load_words(words_path)

    def _load_words(self, words_path: Optional[str] = None):
        try:
            if words_path is not None:
                if not os.path.exists(words_path):
                    raise FileNotFoundError(f"Words data file not found at: {words_path}")
                with open(words_path, "r", encoding="utf-8") as file:
                    word_data = json.load(file)
            else:
                with importlib.resources.files("textarena.envs.TwentyQuestions").joinpath(
                    "twenty_questions_words.json"
                ).open("r", encoding="utf-8") as file:
                    word_data = json.load(file)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load words data: {exc}") from exc

        category = "hardcore" if self.hardcore else "basic"
        words = word_data.get(category) if isinstance(word_data, dict) else None
        if not isinstance(words, dict) or not words:
            raise ValueError(f"No word categories found for difficulty level '{category}'.")
        if any(
            not isinstance(theme, str)
            or not theme.strip()
            or not isinstance(theme_words, list)
            or not theme_words
            or any(not isinstance(word, str) or not word.strip() for word in theme_words)
            or len({word.strip().casefold() for word in theme_words}) != len(theme_words)
            for theme, theme_words in words.items()
        ):
            raise ValueError(f"Invalid word data for difficulty level '{category}'.")
        return words

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def render(self, player_id: int) -> str:
        return self.get_board_str()

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    @staticmethod
    def _copy_resource(resource):
        try:
            return copy.deepcopy(resource), True
        except Exception:
            return None, False

    def _restore_gamemaster_checkpoint(self, original, checkpoint, copied: bool):
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
                self.gamemaster = original
            else:
                self.gamemaster = checkpoint
        elif original is None:
            self.gamemaster = None

    def snapshot(self) -> Dict[str, Any]:
        snapshot = super().snapshot()
        resource, copied = self._copy_resource(self.gamemaster)
        snapshot["gamemaster_resource"] = {"copied": copied, "value": resource}
        return snapshot

    def restore(self, snapshot: Dict[str, Any]):
        super().restore(snapshot)
        resource = snapshot.get("gamemaster_resource", {})
        if resource.get("copied"):
            self.gamemaster = copy.deepcopy(resource["value"])

    # Convenience accessors; the per-episode data lives in game_state.
    @property
    def game_theme(self) -> str:
        return self.game_state["game_theme"]

    @property
    def game_word(self) -> str:
        return self.game_state["target_word"]

    @property
    def gamemaster_context(self) -> str:
        return self.game_state["gamemaster_context"]

    @property
    def gamemaster_history(self) -> List:
        return self.game_state["gamemaster_history"]

    def _get_gamemaster(self):
        if self.gamemaster is None:
            try:
                self.gamemaster = ta.agents.OpenRouterAgent(model_name="openai/gpt-4o")
            except (ImportError, ValueError) as exc:
                raise RuntimeError(
                    "TwentyQuestions questions require OpenRouter. Install the OpenAI dependency "
                    "and set OPENROUTER_API_KEY, or inject a gamemaster."
                ) from exc
        return self.gamemaster

    def get_gamemaster_response(self, action: str) -> str:
        # Validate gamemaster state
        if self.gamemaster_context is None: raise ValueError("Gamemaster context is not set.")
        if self.gamemaster_history is None: raise ValueError("History is not set.")
        if self.gamemaster_options is None: raise ValueError("Gamemaster options are not set.")
        options = ", ".join(f"'{opt}'" for opt in self.gamemaster_options) # Format available response options
        history = "\n".join(f"Q: {q}\nA: {a}" for q, a in self.gamemaster_history) # Construct conversation history
        prompt = (f"{self.gamemaster_context}\n{history}\n\nQ: {action}\nOptions: {options}\n\nPlease respond with the most appropriate option.") # Create prompt
        response = self._get_gamemaster()(prompt)
        if not isinstance(response, str) or len(response) > self.max_gamemaster_response_chars:
            raise ValueError("gamemaster returned an invalid answer")
        match = self._GAMEMASTER_RESPONSE_RE.fullmatch(response)
        if match is None:
            raise ValueError("gamemaster returned an invalid answer")
        answer = re.sub(r"\s+", " ", match.group("answer")).replace("’", "'").casefold()
        normalized = next(
            option for option in self.gamemaster_options if answer == option.casefold()
        )
        self.gamemaster_history.append((action, normalized))
        return normalized

    def setup(self) -> Dict[str, Any]:
        ## load the game word
        game_theme = self.rng.choice(list(self.word_list.keys()))
        game_word = self.rng.choice(self.word_list[game_theme])
        ## the gamemaster context
        gamemaster_context = (
            f"You are the gamemaster for the game of '20 Questions'.\n"
            f"You will provide responses to the players' questions that guides them into guessing the target word: {game_word}\n"
        )
        return {
            "target_word": game_word, "game_theme": game_theme, "rendered_text": "Game word: ???",
            "gamemaster_context": gamemaster_context, "gamemaster_history": [], "history": [],
            "question_limit": self.max_turns - 1, "target_revealed": False,
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id}. You are playing 20 Questions ({'Hardcore' if self.hardcore else 'Basic'}).\n"
            f"The gamemaster has chosen an object that can be one or two words. This object is related to {self.game_theme}. You have to guess this object by asking yes-or-no questions.\n"
            f"The game will last for a maximum of {self.max_turns - 1} questions. After that, the gamemaster will prompt you to make a guess.\n"
            "You may ask your question in any manner.\n"
            "Then, to make your final word guess, reply with 'guess <word>', e.g. 'guess plane', 'guess diving bell'.\n"
            "As you play, the history of your questions and gamemaster's responses will be displayed."
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(action, str) or not action.strip():
            return self.invalid("Ask a non-empty question or submit 'guess <word>'.")
        if len(action) > self.max_action_chars:
            return self.invalid(f"Questions and guesses are limited to {self.max_action_chars} characters.")
        if self._EMPTY_GUESS_RE.fullmatch(action):
            return self.invalid("A guess must include a word after 'guess'.")
        guess_match = self._GUESS_RE.fullmatch(action)
        legacy_match = self._LEGACY_GUESS_RE.fullmatch(action)
        if guess_match is None and legacy_match is None:
            if self.state.turn >= self.max_turns - 1:
                return self.invalid("The question budget is exhausted; submit 'guess <word>'.")
            original_gamemaster = self.gamemaster
            checkpoint, copied = self._copy_resource(original_gamemaster)
            try:
                gamemaster_response = self.get_gamemaster_response(action.strip())
            except Exception:
                self._restore_gamemaster_checkpoint(original_gamemaster, checkpoint, copied)
                return self.retryable("The gamemaster could not answer the question.")
            self.game_state["history"].append((action, gamemaster_response))
            if self.state.turn == self.max_turns - 2:
                gamemaster_response += "\nYou have run out of questions. What is your final guess?"
            self.broadcast(gamemaster_response, ta.ObservationType.GAME_MESSAGE)
            return None
        ## the action is a guess
        action_text = (guess_match or legacy_match).group("guess")
        action_text = re.sub(r"\s+", " ", action_text.strip()).casefold()
        target = re.sub(r"\s+", " ", self.game_word.strip()).casefold()
        self.game_state["target_revealed"] = True
        self.game_state["rendered_text"] = f"Game word: {self.game_word}"
        if action_text == target:
            return self.outcome({0: 1}, reason="Congratulations! You guessed the word.")
        return self.outcome({0: 0}, reason="Invalid guess. You guessed incorrectly.")

    def on_turn_limit(self) -> ta.Outcome:
        self.game_state["target_revealed"] = True
        self.game_state["rendered_text"] = f"Game word: {self.game_word}"
        return self.outcome({0: 0}, reason="The turn limit has been reached")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        self.game_state["target_revealed"] = True
        self.game_state["rendered_text"] = f"Game word: {self.game_word}"
        return super().on_invalid_limit(player_id, reason)
