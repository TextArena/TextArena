import json, os, re
import importlib.resources
import unicodedata
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.TruthAndDeception.renderer import create_board_str


class TruthAndDeceptionEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    snapshot_excluded_attributes = ("facts_data",)

    def __init__(self, max_turns: int = 6, data_path: Optional[str] = None):
        if (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns < 2
            or max_turns % 2 != 0
        ):
            raise ValueError("max_turns must be an even integer of at least 2 so the Guesser takes the final turn.")
        self.max_turns = max_turns
        self._load_facts(data_path=data_path)
        self.guess_fact1_pattern = re.compile(r"^\s*(?:Fact\s+1|\[\s*Fact\s+1\s*\])\s*$", re.IGNORECASE)
        self.guess_fact2_pattern = re.compile(r"^\s*(?:Fact\s+2|\[\s*Fact\s+2\s*\])\s*$", re.IGNORECASE)

    def get_board_str(self):
        return create_board_str(game_state=self.game_state, reveal_answer=self.state.done)

    def _load_facts(self, data_path: Optional[str]) -> None:
        if data_path is not None:
            if not os.path.isfile(data_path):
                raise FileNotFoundError(f"Facts data file not found at: {data_path}")
            with open(data_path, "r", encoding="utf-8") as file:
                facts_data = json.load(file)
        else:
            with importlib.resources.files("textarena.envs.TruthAndDeception").joinpath("facts.json").open(
                "r", encoding="utf-8"
            ) as file:
                facts_data = json.load(file)

        if not isinstance(facts_data, list) or not facts_data:
            raise ValueError("Facts data must be a non-empty JSON list.")
        for entry in facts_data:
            facts = entry.get("facts") if isinstance(entry, dict) else None
            if (
                not isinstance(facts, dict)
                or not isinstance(facts.get("fact1"), str)
                or not facts["fact1"].strip()
                or not isinstance(facts.get("fact2"), str)
                or not facts["fact2"].strip()
                or entry.get("correct_fact") not in {"fact1", "fact2"}
            ):
                raise ValueError("Each facts entry must contain two non-empty facts and a valid correct_fact.")
            normalized_fact1 = " ".join(unicodedata.normalize("NFKC", facts["fact1"]).casefold().split())
            normalized_fact2 = " ".join(unicodedata.normalize("NFKC", facts["fact2"]).casefold().split())
            if normalized_fact1 == normalized_fact2:
                raise ValueError("The two facts in an entry must be distinct.")
        self.facts_data = facts_data

    def setup(self) -> Dict[str, Any]:
        selected_facts = self.rng.choice(self.facts_data)
        facts = [
            (selected_facts["facts"]["fact1"], selected_facts["correct_fact"] == "fact1"),
            (selected_facts["facts"]["fact2"], selected_facts["correct_fact"] == "fact2"),
        ]
        self.rng.shuffle(facts)
        return {
            "fact1": {"fact": facts[0][0], "is_correct": facts[0][1]},
            "fact2": {"fact": facts[1][0], "is_correct": facts[1][1]},
        }

    def roles(self) -> Dict[int, str]:
        return {0: "Deceiver", 1: "Guesser"}

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        role = self.state.role_mapping[player_id]
        prompt = f"You are Player {player_id}, and you are the {role} in the 'Truth and Deception' game.\n"
        if role == "Deceiver":
            prompt += (
                f"You know which of the following two facts is correct:\n"
                f"Fact 1: {game_state['fact1']['fact']} ({'correct' if game_state['fact1']['is_correct'] else 'wrong'})\n"
                f"Fact 2: {game_state['fact2']['fact']} ({'correct' if game_state['fact2']['is_correct'] else 'wrong'})\n"
                "Your goal is to convince the other player to choose the incorrect fact.\n"
                f"The first {self.max_turns - 1} total turns are conversation.\n"
                "On the final turn, the Guesser must reply with exactly 'Fact 1' or 'Fact 2'.\n"
                "On your turn, simply type your message."
            )
        elif role == "Guesser":
            prompt += (
                f"You need to determine which of the following two facts is correct:\n"
                f"Fact 1: {game_state['fact1']['fact']}\n"
                f"Fact 2: {game_state['fact2']['fact']}\n"
                f"The first {self.max_turns - 1} total turns are conversation.\n"
                "On the final turn, reply with exactly 'Fact 1' or 'Fact 2'.\n"
                "On your turn, simply type your message."
            )
        else:
            raise ValueError(f"Unexpected role mapping: {role}. Expected 'Deceiver' or 'Guesser'.")
        return prompt

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if self.state.turn == self.max_turns - 2:  # check if the guessing phase has started
            self.broadcast("Now guess which fact is correct by replying with 'Fact 1' or 'Fact 2'.", ta.ObservationType.GAME_MESSAGE)
        elif self.state.turn == self.max_turns - 1:
            normalized_action = unicodedata.normalize("NFKC", action)
            normalized_action = "".join(
                char
                for char in normalized_action
                if unicodedata.category(char) != "Cf"
            )
            guessed_fact1 = self.guess_fact1_pattern.search(normalized_action) is not None
            guessed_fact2 = self.guess_fact2_pattern.search(normalized_action) is not None
            if guessed_fact1 or guessed_fact2: # evaluate guess
                if (guessed_fact1 and self.game_state["fact1"]["is_correct"]) or (guessed_fact2 and self.game_state["fact2"]["is_correct"]):
                    return self.winner(player_id, reason=f"Player {player_id} guessed correct fact.") # correct guess
                return self.winner(1 - player_id, reason=f"Player {player_id} guessed the wrong fact.") # wrong guess
            return self.invalid(f"Player {player_id} did not make their guess in the correct format.")
        return None
