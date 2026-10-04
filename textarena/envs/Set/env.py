import copy
import itertools
import re
from typing import Dict, Tuple, Optional, Any, Union

import textarena as ta

# game constants
_NUMBERS = ["one", "two", "three"]
_COLORS = ["red", "green", "purple"]
_FILLS = ["open", "striped", "solid"]
_SHAPES = ["oval", "diamond", "squiggle"]

# one card is [number, color, fill, shape]
Card = Tuple[str, str, str, str]

# for each attribute, a set must have 3 different values or 1 value
def _is_set(cards: Tuple[Card, Card, Card]):
    numbers, colors, fills, shapes = zip(*cards)
    return len(set(numbers)) in [1, 3] and len(set(colors)) in [1, 3] and len(set(fills)) in [1, 3] and len(set(shapes)) in [1, 3]

def _get_missing_card(cards: Tuple[Card, Card]) -> Card:
    # determine the third card missing that would make a full set
    numbers, colors, fills, shapes = zip(*cards)
    number = numbers[0] if numbers[0] == numbers[1] else next(iter(set(_NUMBERS) - set(numbers)))
    color = colors[0] if colors[0] == colors[1] else next(iter(set(_COLORS) - set(colors)))
    fill = fills[0] if fills[0] == fills[1] else next(iter(set(_FILLS) - set(fills)))
    shape = shapes[0] if shapes[0] == shapes[1] else next(iter(set(_SHAPES) - set(shapes)))

    return number, color, fill, shape

def _has_set(cards: list[Card]):
    # check if a list of cards has a set
    pairs = itertools.combinations(cards, 2)
    for pair in pairs:
        missing_card = _get_missing_card(pair)
        if missing_card in cards:
            return True
    return False

class SetEnv(ta.GameEnv):
    min_players = 1
    max_players = 1

    def __init__(self, seed: int = 42):
        # pre-generate all valid sets
        self.deck = list(itertools.product(_NUMBERS, _COLORS, _FILLS, _SHAPES))
        all_pairs = [(x, y) for (x, y) in itertools.product(self.deck, self.deck) if x != y]
        self.all_sets = set([(*pair, _get_missing_card(pair)) for pair in all_pairs])
        self.max_turns = 20

    def setup(self) -> Dict[str, Any]:
        _initial_deck = copy.deepcopy(self.deck)
        self.rng.shuffle(_initial_deck)
        _initial_board = [_initial_deck.pop() for _ in range(12)]
        return {
            "deck": _initial_deck,
            "board": _initial_board,
            "found_cards": [],
            "score": 0,
            "num_turns": 0,
        }

    def prompt(self, player_id: int) -> str:
        return (
            "You are playing a single-player game of Set. "
            "Your goal is to find as many Sets as you can in 20 turns, without making mistakes. "
            "The board contains a numbered list of 12 or more cards with (number, color, fill, shape). "
            "A Set is a set of 3 cards where, for each attribute, they're all 3 the same, "
            "or all 3 different. For instance, 'one red open squiggle', "
            "'two green open squiggle', 'three purple open squiggle' would be a Set. "
            "Each turn, you select a list of 3 cards from the board by their numbered index. "
            "For example, '1, 4, 11'. If it is a Set, you score and the cards are replaced. "
            'If it is not a Set, that turn was wasted. The game ends when you run out of turns. '
            "Reply with exactly the 3 card indices, e.g. '2, 4, 8'."
        )

    def on_start(self):
        self._ensure_set_available()
        self._observe_state()

    def _parse_action(self, action: str) -> Optional[Tuple[int, int, int]]:
        # Board indices can never exceed two digits. A small bounded allowance
        # keeps malformed digit floods from reaching Python's integer parser.
        m = re.fullmatch(
            r"\[?\s*([0-9]{1,6})\s*[,\s]\s*([0-9]{1,6})"
            r"\s*[,\s]\s*([0-9]{1,6})\s*\]?",
            action.strip(),
        )
        if m is None:
            return None
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        parsed = self._parse_action(move)

        board = self.game_state["board"]
        max_idx = len(board)
        if not parsed:
            return self.invalid("Invalid action format. Reply with 3 card indices like '1, 4, 11'.")
        elif min(parsed) < 1 or max(parsed) > max_idx:
            return self.invalid(f"Invalid action. Card indices must be between 1 and {max_idx}.")
        elif len(set(parsed)) != 3:
            return self.invalid("Invalid action. Select three distinct card indices.")

        self.game_state["num_turns"] += 1
        cards = board[parsed[0]-1], board[parsed[1]-1], board[parsed[2]-1]
        if _is_set(cards):
            self.broadcast("You found a Set! +1 point!", ta.ObservationType.GAME_MESSAGE)
            self.game_state["score"] += 1

            # remove from the board
            for idx in sorted(parsed, reverse=True):
                self.game_state["found_cards"].append(board.pop(idx-1))

            # if < 12 cards, deal up to 12
            while len(board) < 12 and self.game_state['deck']:
                card = self.game_state['deck'].pop()
                self.game_state['board'].append(card)

            self._ensure_set_available()
            self._observe_state()
            if not _has_set(board) and not self.game_state["deck"]:
                return self.outcome(
                    {0: self.game_state["score"]},
                    reason="No sets remain and the deck is empty.",
                )
        else:
            self.broadcast("That is not a Set. No point for you.", ta.ObservationType.GAME_MESSAGE)
        if not _has_set(board) and not self.game_state["deck"]:
            return self.outcome(
                {0: self.game_state["score"]},
                reason="No sets remain and the deck is empty.",
            )
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome({0: self.game_state["score"]}, reason="You've taken 20 turns. The game is over.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome(
            {0: self.game_state["score"]},
            reason=f"Invalid Move: {reason}",
        )

    def _observe_state(self):
        gs = self.game_state
        assert gs is not None, "no game state"
        board = "=== BOARD ==="
        for idx, card in enumerate(gs['board']):
            board += f"\n{idx+1}: {' '.join(card)}"
        self.broadcast(board, ta.ObservationType.GAME_BOARD)

    def _ensure_set_available(self) -> bool:
        """Deal groups of up to three until the board has a Set or the deck is empty."""
        gs = self.game_state
        while not _has_set(gs["board"]) and gs["deck"]:
            cards_dealt = min(3, len(gs["deck"]))
            for _ in range(cards_dealt):
                gs["board"].append(gs["deck"].pop())
            self.broadcast(
                f"No valid sets found on board. Dealt {cards_dealt} additional cards.",
                ta.ObservationType.GAME_MESSAGE,
            )
        return _has_set(gs["board"])

    def get_board_str(self) -> str:
        """Return the current board state as a string for rendering."""
        if not hasattr(self, 'state') or not self.state.game_state:
            return "Game not started"

        gs = self.game_state
        board = f"=== BOARD === (Score: {gs['score']}, Turns: {gs['num_turns']}/20)"
        for idx, card in enumerate(gs['board']):
            board += f"\n{idx+1}: {' '.join(card)}"
        return board
