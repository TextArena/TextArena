import re
import unicodedata
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.utils.word_lists import get_basic_english_words, get_headwords

# Ogden's 100 "operations": the verbs, prepositions, pronouns, conjunctions and adverbs of
# Basic English. They are unusable secret words, since any conversation says them by accident.
OGDEN_OPERATIONS = frozenset(
    """
    come get give go keep let make put seem take be do have say see send may will
    about across after against among at before between by down from in off on over through to under up with
    as for of till than a the all any every little much no other some such that this i he you who
    and because but or if though while how when where why again ever far forward here near now out still
    then there together well almost enough even not only quite so very tomorrow yesterday north south east
    west please yes
    """.split()
)


class DontSayItEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    snapshot_excluded_attributes = ("word_list",)

    @staticmethod
    def _normalize_for_match(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(
            char for char in normalized if unicodedata.category(char) != "Cf"
        )

    def __init__(self, max_turns: Optional[int], hardcore: Optional[bool] = False):
        """
        Args:
            hardcore (bool): If True, draw secret words from every headword of the bundled dictionaries;
                otherwise from the 750 nouns and adjectives of Ogden's Basic English. Both lists are
                bundled, so a seed picks the same words on every machine, with or without NLTK data.
            max_turns (int): Maximum number of turns before the game ends in a draw.
        """
        if max_turns is not None and (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns < 2
            or max_turns % 2 != 0
        ):
            raise ValueError("max_turns must be an even integer of at least 2, or None.")
        if not isinstance(hardcore, bool):
            raise ValueError("hardcore must be a boolean.")
        self.hardcore = hardcore
        if hardcore:
            self.word_list = sorted(get_headwords())
        else:
            self.word_list = sorted(word for word in get_basic_english_words() if word not in OGDEN_OPERATIONS)
        self.max_turns = max_turns

    def setup(self) -> Dict[str, Any]:
        first, second = self.rng.sample(self.word_list, 2)
        return {"target_words": {0: first, 1: second}}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a game of DontSayIt.\nYour secret word is: '{self.game_state['target_words'][player_id]}'.\n"
            "Your goal is to get the other player to say your secret word before you say theirs.\n"
            "You can converse freely, but try to be subtle to avoid making it obvious.\n On your turn, simply type your message.\n"
            + (
                f"The game lasts for {self.max_turns} turns in total.\n"
                if self.max_turns is not None
                else "The game has no turn limit.\n"
            )
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        opponent_word = self._normalize_for_match(
            self.game_state["target_words"][1 - player_id]
        )
        normalized_action = self._normalize_for_match(action)
        if re.search(rf"(?<!\w){re.escape(opponent_word)}(?!\w)", normalized_action):
            return self.winner(1 - player_id, reason=f"Player {player_id} mentioned the opponent's secret word.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.draw(reason="The turn limit has been reached")
