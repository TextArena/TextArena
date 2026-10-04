import random
from typing import List, Optional, Tuple


class Card:
    """Represents a single playing card."""

    def __init__(self, rank: int, suit: str) -> None:
        self.rank = rank  # 1-13 (1 = Ace, 11=Jack, 12=Queen, 13=King)
        self.suit = suit  # 'H', 'D', 'C', 'S'

    @property
    def color(self) -> str:
        return "red" if self.suit in ("D", "H", "♦️", "♥️") else "black"

    def __str__(self) -> str:
        rank_str = {1: "A", 11: "J", 12: "Q", 13: "K"}.get(self.rank, str(self.rank))
        return f"{rank_str}{self.suit}"

    def __repr__(self) -> str:
        return str(self)


class KlondikeGame:
    """Implements the piles and move rules of a Klondike solitaire game."""

    def __init__(self, seed: Optional[int] = None, draw_count: int = 3) -> None:
        """
        Initialize the game. If seed is provided, shuffles the deck using that seed
        to allow reproducible games. draw_count determines how many cards are drawn
        from the stock at a time (1 or 3).
        """
        if (
            not isinstance(draw_count, int)
            or isinstance(draw_count, bool)
            or draw_count not in (1, 3)
        ):
            raise ValueError("draw_count must be either 1 or 3")
        self.draw_count = draw_count
        # Create a deck of cards
        self.deck: List[Card] = [
            Card(rank, suit) for suit in ("♣️", "♦️", "♥️", "♠️") for rank in range(1, 14)
        ]
        self.rng = random.Random(seed)
        self.rng.shuffle(self.deck)
        # Data structures
        self.tableau: List[
            List[Tuple[Card, bool]]
        ] = []  # Each element: (Card, face_up)
        # Four foundation piles (F1..F4). Each pile accepts an Ace to start,
        # then must build up by suit from A->K. Piles are not pre-assigned to suits.
        self.foundations: List[List[Card]] = [[] for _ in range(4)]
        self.stock: List[
            Tuple[Card, bool]
        ] = []  # (Card, face_up). Cards in stock are always face_down
        self.waste: List[
            Tuple[Card, bool]
        ] = []  # (Card, face_up). Waste cards are face_up
        self.setup_game()

    def setup_game(self) -> None:
        """Deal cards into tableau piles and the stock."""
        deck_iter = iter(self.deck)
        # Create tableau piles of increasing sizes; last card in each is face-up
        for pile_index in range(7):
            pile: List[Tuple[Card, bool]] = []
            for j in range(pile_index + 1):
                card = next(deck_iter)
                # All but the last card in the pile are face down
                face_up = j == pile_index
                pile.append((card, face_up))
            self.tableau.append(pile)
        # Remaining cards go to stock (face down). We maintain stock so that
        # self.stock.pop() returns the next card to draw. Since deck_iter yields
        # the remaining cards in top-to-bottom order, we reverse them so that
        # pop() returns the original next (top) card first.
        remaining = list(deck_iter)
        self.stock = [(card, False) for card in reversed(remaining)]

    def draw(self) -> bool:
        """Draw up to draw_count cards from stock to waste.

        - If stock is empty and waste is not, recycle waste into stock (face down) then draw.
        - If stock has fewer than draw_count cards, draw whatever remains.
        Returns True if any card was drawn; False if both stock and waste are empty.
        """
        # If stock is empty, attempt to recycle waste once
        if not self.stock:
            if not self.waste:
                return False
            # Recycle waste back into stock: reverse order and flip to face_down
            self.stock = [(card, False) for card, _ in reversed(self.waste)]
            self.waste.clear()

        # Draw up to draw_count cards
        to_draw = min(self.draw_count, len(self.stock))
        drew_any = False
        for _ in range(to_draw):
            card, _ = self.stock.pop()
            self.waste.append((card, True))
            drew_any = True
        return drew_any

    def can_move_to_foundation_pile(self, card: Card, f_index: int) -> bool:
        """Check if card can be placed onto the specific foundation pile index (0..3)."""
        if not (0 <= f_index < 4):
            return False
        pile = self.foundations[f_index]
        if not pile:
            return card.rank == 1
        top = pile[-1]
        return top.suit == card.suit and card.rank == top.rank + 1

    def move_from_waste_to_foundation_at(self, dest_index: int) -> bool:
        """Attempt to move the top waste card to a specific foundation pile index."""
        if not self.waste:
            return False
        card, _ = self.waste[-1]
        if not self.can_move_to_foundation_pile(card, dest_index):
            return False
        self.waste.pop()
        self.foundations[dest_index].append(card)
        return True

    def move_from_tableau_to_foundation_at(
        self, src_index: int, dest_index: int
    ) -> bool:
        """Attempt to move the top card of a tableau pile to a specific foundation index."""
        if not (0 <= src_index < len(self.tableau)):
            return False
        pile = self.tableau[src_index]
        if not pile:
            return False
        card, face_up = pile[-1]
        if not face_up:
            return False
        if not self.can_move_to_foundation_pile(card, dest_index):
            return False
        pile.pop()
        self.foundations[dest_index].append(card)
        if pile and not pile[-1][1]:
            c, _ = pile[-1]
            pile[-1] = (c, True)
        return True

    def can_place_on_tableau(self, dest_top: Optional[Card], card: Card) -> bool:
        """Check if the card can be placed onto the destination tableau top card."""
        if dest_top is None:
            # Empty pile: only King can be placed
            return card.rank == 13
        # Otherwise, card rank must be dest.rank - 1 and opposite color
        return dest_top.rank == card.rank + 1 and dest_top.color != card.color

    def move_waste_to_tableau(self, dest_index: int) -> bool:
        """Move the top card from waste to the specified tableau pile."""
        if not self.waste:
            return False
        if not (0 <= dest_index < len(self.tableau)):
            return False
        card, _ = self.waste[-1]
        dest_pile = self.tableau[dest_index]
        dest_top_card = dest_pile[-1][0] if dest_pile else None
        if self.can_place_on_tableau(dest_top_card, card):
            # perform move
            self.waste.pop()
            dest_pile.append((card, True))
            return True
        return False

    def move_tableau_to_tableau(
        self, src_index: int, count: int, dest_index: int
    ) -> bool:
        """Move `count` cards from one tableau pile to another."""
        if src_index == dest_index:
            return False
        if not (
            0 <= src_index < len(self.tableau) and 0 <= dest_index < len(self.tableau)
        ):
            return False
        src_pile = self.tableau[src_index]
        dest_pile = self.tableau[dest_index]
        if count <= 0 or count > len(src_pile):
            return False
        # The slice to move must be all face up
        moving_slice = src_pile[-count:]
        if not all(face_up for _, face_up in moving_slice):
            return False
        # A movable tableau run must itself build down in alternating colors.
        for (lower, _), (upper, _) in zip(moving_slice, moving_slice[1:]):
            if lower.rank != upper.rank + 1 or lower.color == upper.color:
                return False
        bottom_card_to_move = moving_slice[0][0]
        dest_top_card = dest_pile[-1][0] if dest_pile else None
        if not self.can_place_on_tableau(dest_top_card, bottom_card_to_move):
            return False
        # perform move
        self.tableau[src_index] = src_pile[:-count]
        self.tableau[dest_index] += moving_slice
        # flip new top card on src if necessary
        if self.tableau[src_index] and not self.tableau[src_index][-1][1]:
            c, _ = self.tableau[src_index][-1]
            self.tableau[src_index][-1] = (c, True)
        return True

    def is_won(self) -> bool:
        """Check if all foundations are complete (each has 13 cards)."""
        return all(len(pile) == 13 for pile in self.foundations)
