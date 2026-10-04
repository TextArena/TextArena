import copy
import importlib.resources
import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Union

import textarena as ta

_ARTICLES = frozenset({"a", "an", "the"})


def _answer_key(text: str) -> str:
    """Letters and digits only, without accents or a leading article."""
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text).casefold())
    tokens = re.findall(r"[^\W_]+", "".join(char for char in decomposed if not unicodedata.combining(char)))
    if len(tokens) > 1 and tokens[0] in _ARTICLES:
        tokens = tokens[1:]
    return "".join(tokens)


class GuessWhoEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    snapshot_excluded_attributes = ("gamemaster",)
    max_action_chars = 4_000
    max_gamemaster_response_chars = 256
    _GUESS_RE = re.compile(r"^\s*guess(?:\s+|:\s*)(?P<guess>.+?)\s*$", re.IGNORECASE)
    _EMPTY_GUESS_RE = re.compile(r"^\s*guess\s*:?\s*$", re.IGNORECASE)
    _GAMEMASTER_RESPONSE_RE = re.compile(
        r"""^\s*(?:answer\s*:\s*)?["'“”]?(?P<answer>yes|no|i\s+don['’]t\s+know)["'“”]?[.!]?\s*$""",
        re.IGNORECASE,
    )

    def __init__(
        self,
        max_turns: int = 40,
        gamemaster: Optional[Any] = None,
        characters_path: Optional[str] = None,
    ):
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 2:
            raise ValueError("max_turns must be an integer of at least 2 (questions plus a final guess).")
        if gamemaster is not None and not callable(gamemaster):
            raise TypeError("gamemaster must be callable.")
        self.max_turns = max_turns
        # Delay creation of the network-backed default until a question is asked.
        self.gamemaster = gamemaster
        self.gamemaster_options = ["Yes", "No", "I don't know"]
        self.characters = self._load_characters(characters_path)

    def _load_characters(self, characters_path: Optional[str] = None):
        try:
            if characters_path is not None:
                if not os.path.exists(characters_path):
                    raise FileNotFoundError(f"Characters data file not found at: {characters_path}")
                with open(characters_path, "r", encoding="utf-8") as file:
                    characters = json.load(file)
            else:
                with importlib.resources.files("textarena.envs.GuessWho").joinpath(
                    "characters.json"
                ).open("r", encoding="utf-8") as file:
                    characters = json.load(file)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load characters data: {exc}") from exc

        required = {
            "name", "age_range", "gender", "hair_style", "hair_color", "eye_color",
            "accessories", "facial_hair", "complexion", "skin_tone", "smile_type",
            "clothing_style", "hair_texture", "eyewear_style", "nose_shape", "ear_size",
            "cheek_features", "hat_type",
        }
        if (
            not isinstance(characters, list)
            or not characters
            or any(not isinstance(char, dict) or not required <= char.keys() for char in characters)
            or any(
                any(not isinstance(char[field], str) or not char[field].strip() for field in required - {"accessories"})
                or not isinstance(char["accessories"], list)
                or any(not isinstance(item, str) or not item.strip() for item in char["accessories"])
                for char in characters
            )
            or len({_answer_key(char["name"]) for char in characters} - {""}) != len(characters)
            or any(
                (char["hat_type"].strip().casefold() != "none")
                != any(accessory.strip().casefold() == "hat" for accessory in char["accessories"])
                for char in characters
            )
        ):
            raise ValueError(
                "Characters data must be a non-empty list with unique names, all required traits, "
                "and consistent hat accessories."
            )
        return characters

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
    def target_character(self) -> Dict[str, Any]:
        return self.game_state["target_character"]

    @property
    def gamemaster_context(self) -> str:
        return self.game_state["gamemaster_context"]

    @property
    def gamemaster_history(self) -> List:
        return self.game_state["gamemaster_history"]

    def get_board_str(self) -> str:
        target_name = self.target_character["name"] if self.state.done else "???"
        lines = [
            "Guess Who",
            f"Target Character: {target_name}",
            f"Questions Asked: {len(self.gamemaster_history)} / {self.max_turns - 1}",
        ]
        if self.gamemaster_history:
            lines.append("History:")
            for index, (question, answer) in enumerate(self.gamemaster_history, start=1):
                lines.append(f"{index}. Q: {question}")
                lines.append(f"   A: {answer}")
        else:
            lines.append("No questions asked yet.")
        return "\n".join(lines)

    def render(self, player_id: int) -> str:
        return self.get_board_str()

    def _get_gamemaster(self):
        if self.gamemaster is None:
            try:
                self.gamemaster = ta.agents.OpenRouterAgent(model_name="openai/gpt-4o")
            except (ImportError, ValueError) as exc:
                raise RuntimeError(
                    "GuessWho questions require OpenRouter. Install the OpenAI dependency "
                    "and set OPENROUTER_API_KEY, or inject a gamemaster."
                ) from exc
        return self.gamemaster

    def get_gamemaster_response(self, action: str) -> str:
        """ Get the gamemaster's response based on the provided action """
        # Validate gamemaster state
        if self.gamemaster_context is None:     raise ValueError("Gamemaster context is not set.")
        if self.gamemaster_history is None:     raise ValueError("History is not set.")
        if self.gamemaster_options is None:     raise ValueError("Gamemaster options are not set.")
        options = ", ".join(f"'{opt}'" for opt in self.gamemaster_options) # Format available response options
        history = "\n".join(f"Q: {q}\nA: {a}" for q, a in self.gamemaster_history) # Construct conversation history
        prompt = f"{self.gamemaster_context}\n{history}\n\nQ: {action}\nOptions: {options}\n\nPlease respond with the most appropriate option." # Create prompt
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
        target_character = copy.deepcopy(self.rng.choice(self.characters))
        gamemaster_context = ( ## the gamemaster context
            f"You are the gamemaster for the game of 'Guess Who'.\n"
            f"You will provide responses to the player's questions that guides them into guessing the target character with the following name and traits: {target_character}.\n"
        )
        return {"target_character": target_character, "gamemaster_context": gamemaster_context, "gamemaster_history": []}

    def prompt(self, player_id: int) -> str:
        """ Generate the player prompt """
        return (
            f"You are Player {player_id}. You are playing Guess Who.\n"
            "The gamemaster has chosen one target character from the list of characters that you will be shown below.\n"
            "You have to guess the target character by asking yes-or-no questions about the target character's traits.\n"
            "You can ask questions like 'Is the character male?' or 'Does the character have a beard?'. "
            "Any message containing a '?' is treated as a question.\n"
            f"You may ask up to {self.max_turns - 1} questions; the turn after that is reserved for your guess.\n"
            "You can also guess the name of the target character at any time by replying with 'guess <name>', "
            f"e.g. 'guess {self.characters[0]['name']}'. You get exactly one guess: naming the target wins, and naming "
            "any other character from the list ends the game without a win.\n"
            "As you play, the history of your questions and gamemaster's responses will be displayed.\n"
            "Here is the list of characters you can ask questions about:\n"
        ) + self._characters_to_string()

    def _characters_to_string(self) -> str:
        formatted_descriptions = []
        for i, char in enumerate(self.characters, start=1):
            # Format the description in a narrative style
            other_accessories = [
                accessory for accessory in char["accessories"] if accessory.casefold() != "hat"
            ]
            accessories = ", ".join(other_accessories) if other_accessories else "no other accessories"
            hat = f"a {char['hat_type']} hat" if char["hat_type"].casefold() != "none" else "no hat"
            description = (
                f"{i}. {char['name']} is a {char['age_range']} {char['gender']} with {char['hair_style']} "
                f"{char['hair_color']} hair and {char['eye_color']} eyes. {char['name']} has a {char['complexion']} complexion, "
                f"{char['skin_tone']} skin tone, and {char['smile_type']} smile. They have {accessories}, wear {hat}, "
                f"have {char['facial_hair']} facial hair, and their clothing style is {char['clothing_style']}. "
                f"{char['name']} has {char['hair_texture']} hair texture, {char['eyewear_style']} glasses style, "
                f"a {char['nose_shape']} nose, {char['ear_size']} ears, and {char['cheek_features']} on their cheeks."
            )
            formatted_descriptions.append(description)
        return "\n\n".join(formatted_descriptions) # Join all descriptions into a single text block

    def _parse_guess(self, action: str) -> Optional[str]:
        """The guessed name, or None when the message is a question."""
        if "?" in unicodedata.normalize("NFKC", action):
            return None  # e.g. "Guess what, is the character male?" is a question
        match = self._GUESS_RE.fullmatch(action)
        return match.group("guess") if match else None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(action, str) or not action.strip():
            return self.invalid("Ask a non-empty question or submit 'guess <name>'.")
        if len(action) > self.max_action_chars:
            return self.invalid(f"Questions and guesses are limited to {self.max_action_chars} characters.")
        action = self.strip_role_tags(action)
        if self._EMPTY_GUESS_RE.fullmatch(action):
            return self.invalid("A guess must include a character name after 'guess'.")
        guess = self._parse_guess(action)
        if guess is None:
            question = " ".join(action.split())
            if not re.search(r"[^\W_]", question):
                return self.invalid("Ask a yes-or-no question in words or submit 'guess <name>'.")
            if self.state.turn >= self.max_turns - 1:
                return self.invalid("The question budget is exhausted; submit 'guess <name>'.")
            original_gamemaster = self.gamemaster
            checkpoint, copied = self._copy_resource(original_gamemaster)
            try:
                response = self.get_gamemaster_response(question)
            except Exception:
                self._restore_gamemaster_checkpoint(original_gamemaster, checkpoint, copied)
                return self.retryable("The gamemaster could not answer the question.")
            if self.state.turn == self.max_turns - 2:
                response += "\nYou have run out of questions. What is your final guess? Reply with 'guess <name>'."
            self.message(player_id, response, ta.ObservationType.GAME_MESSAGE)
            return None
        ## the action is a guess
        guess_key = _answer_key(guess)
        if guess_key not in {_answer_key(char["name"]) for char in self.characters}:
            return self.invalid(f"'{guess.strip()}' is not one of the characters. Guess a name from the list.")
        target_name = self.target_character["name"]
        if guess_key == _answer_key(target_name):
            return self.outcome({0: 1}, reason=f"Congratulations! Player {player_id} guessed the target character.")
        return self.outcome({0: 0}, reason=f"Wrong guess. The target character was {target_name}.")

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome({0: 0}, reason="The turn limit has been reached.")
