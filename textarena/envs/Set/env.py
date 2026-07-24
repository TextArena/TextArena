import random
import copy
import itertools
from typing import Dict, Tuple, Optional, Any, List, TypeAlias

import textarena as ta

# game constants
_NUMBERS = ["one", "two", "three"]
_COLORS = ["red", "green", "purple"]
_FILLS = ["open", "striped", "solid"]
_SHAPES = ["oval", "diamond", "squiggle"]

# one card is [number, color, fill, shape]
Card: TypeAlias = Tuple[str, str, str, str]

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

class SetEnv(ta.Env):
    def __init__(self, seed: int = 42):
        super().__init__()
        # pre-generate all valid sets
        self.deck = list(itertools.product(_NUMBERS, _COLORS, _FILLS, _SHAPES))
        all_pairs = [(x, y) for (x, y) in itertools.product(self.deck, self.deck) if x != y]
        self.all_sets = set([(*pair, _get_missing_card(pair)) for pair in all_pairs])

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=20)
        _initial_deck = copy.deepcopy(self.deck)
        random.shuffle(_initial_deck)
        _initial_board = [_initial_deck.pop() for _ in range(12)]
        game_state = {"deck": _initial_deck, "board": _initial_board, "score": 0, "num_turns": 0}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_state()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            "You are playing a single-player game of Set. "
            "Your goal is to find as many Sets as you can in 20 turns, without making mistakes. "
            "The board contains a numbered list of 12 or more cards with (number, color, fill, shape). "
            "A Set is a set of 3 cards where, for each attribute, they're all 3 the same, "
            "or all 3 different. For instance, 'one red open squiggle', "
            "'two green open squiggle', 'three purple open squiggle' would be a Set. "
            "Each turn, you select a list of 3 cards from the board by their numbered index. "
            'For example, "[1, 4, 11]". If it is a Set, you score and the cards are replaced. '
            'If it is not a Set, that turn was wasted. The game ends when you run out of turns. '
            'You MUST return your cards in brackets, like [2, 4, 8], or they will not be parsed.'
        )

    def _parse_action(self, action: str) -> Tuple[int, int, int] | None:
        if "[" not in action:
            return None
        action = action.split("[")[1]
        if "]" not in action:
            return None
        action = action.split("]")[0]
        if "," not in action:
            return None
        nums = action.split(",")
        if len(nums) != 3:
            return None
        if not all(x.strip().isdigit() for x in nums):
            return None
        nums = [int(x.strip()) for x in nums]

        return (nums[0], nums[1], nums[2])


    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        parsed = self._parse_action(action)
        
        # check if no valid sets exist on board and deal 3 more cards if needed (BEFORE validating action)
        if not _has_set(self.state.game_state['board']) and self.state.game_state['deck']: # type: ignore
            # deal 3 more cards
            cards_dealt = 0
            while cards_dealt < 3 and self.state.game_state['deck']: # type: ignore
                card = self.state.game_state['deck'].pop() # type: ignore
                self.state.game_state['board'].append(card) # type: ignore
                cards_dealt += 1
            
            if cards_dealt > 0:
                self.state.add_observation(f"No valid sets found on board. Dealt {cards_dealt} additional cards.", observation_type=ta.ObservationType.GAME_MESSAGE)
                # Update the board observation so AI can see the new cards
                self._observe_state()
        
        board = self.state.game_state["board"] # type: ignore
        max_idx = len(board)
        if not parsed:
            self.state.set_invalid_move(reward=0, reason=f"Invalid action format. Return a list of ints like [card1, card2, card3].")
        elif min(parsed) < 1 or max(parsed) > max_idx:
            self.state.set_invalid_move(reward=0, reason=f"Invalid action. Card indices must be between 1 and {max_idx}.")
        else:
            self.state.game_state["num_turns"] += 1 # type: ignore
            cards = board[parsed[0]-1], board[parsed[1]-1], board[parsed[2]-1]
            if _is_set(cards):
                # add message
                self.state.add_observation(f"You found a Set! +1 point!", observation_type=ta.ObservationType.GAME_MESSAGE)

                # score
                self.state.game_state["score"] += 1 # type: ignore

                # remove from the board
                for idx in sorted(parsed, reverse=True):
                    board.pop(idx-1)

                # if < 12 cards, deal up to 12
                while len(board) < 12 and self.state.game_state['deck']: # type: ignore
                    card = self.state.game_state['deck'].pop() # type: ignore
                    self.state.game_state['board'].append(card) # type: ignore
                
                # Update board observation after refilling
                self._observe_state()
            else:
                self.state.add_observation(f"That is not a Set. No point for you.", observation_type=ta.ObservationType.GAME_MESSAGE)


        # finish if 20 turns completed
        if self.state.game_state["num_turns"] >= 20: # type: ignore
            self.state.set_outcome(reward=self.state.game_state["score"], reason="You've taken 20 turns. The game is over.") # type: ignore

        return self.state.step()

    def _observe_state(self):
        gs = self.state.game_state
        assert gs, "no game state"
        board = "=== BOARD ==="
        for idx, card in enumerate(gs['board']):
            board += f"\n{idx+1}: {' '.join(card)}"
        self.state.add_observation(to_id=-1, message=board, observation_type=ta.ObservationType.GAME_BOARD)

    def get_board_str(self) -> str:
        """Return the current board state as a string for rendering."""
        if not hasattr(self.state, 'game_state') or not self.state.game_state:
            return "Game not started"

        gs = self.state.game_state
        board = f"=== BOARD === (Score: {gs['score']}, Turns: {gs['num_turns']}/20)"
        for idx, card in enumerate(gs['board']):
            board += f"\n{idx+1}: {' '.join(card)}"
        return board
