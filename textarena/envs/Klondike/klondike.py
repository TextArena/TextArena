import random
from typing import Dict, List, Optional, Tuple


class Card:
    """Represents a single playing card."""

    def __init__(self, rank: int, suit: str) -> None:
        self.rank = rank  # 1-13 (1 = Ace, 11=Jack, 12=Queen, 13=King)
        self.suit = suit  # 'H', 'D', 'C', 'S'

    @property
    def color(self) -> str:
        return "red" if self.suit in ("♦️", "♥️") else "black"

    def __str__(self) -> str:
        rank_str = {1: "A", 11: "J", 12: "Q", 13: "K"}.get(self.rank, str(self.rank))
        return f"{rank_str}{self.suit}"

    def __repr__(self) -> str:
        return str(self)


class KlondikeGame:
    """Implements a basic Klondike solitaire game with optional auto solver."""

    def __init__(self, seed: Optional[int] = None, draw_count: int = 3) -> None:
        """
        Initialize the game. If seed is provided, shuffles the deck using that seed
        to allow reproducible games. draw_count determines how many cards are drawn
        from the stock at a time (1 or 3 are common). For simplicity, this game uses
        draw_count=1 by default.
        """
        self.draw_count = draw_count
        # Create a deck of cards
        self.deck: List[Card] = [
            Card(rank, suit) for suit in ("♣️", "♦️", "♥️", "♠️") for rank in range(1, 14)
        ]
        if seed is not None:
            random.seed(seed)
        random.shuffle(self.deck)
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

    def print_board(self) -> None:
        """Print the current state of the game board in a machine-friendly horizontal layout.

        Layout:
        - First line shows stock count and waste pile (W) cards.
        - Four foundation piles as F1..F4 (fixed suit order ♣️, ♦️, ♥️, ♠️).
        - Seven tableau piles as T1..T7, each as a single horizontal row.
        """
        suits_order = ["♣️", "♦️", "♥️", "♠️"]

        def pile_to_str(pile: List[Tuple[Card, bool]]) -> str:
            parts = []
            for card, face_up in pile:
                parts.append(str(card) if face_up else "XX")
            return " ".join(parts) if parts else "--"

        # Top line: stock and waste
        stock_count = len(self.stock)
        waste_top = str(self.waste[-1][0]) if self.waste else "--"
        print(f"Stock: {stock_count}")
        print(f"W: {waste_top}")

        # Foundations F1..F4 (not fixed to suit; piles are dynamic)
        for idx in range(1, 5):
            pile = self.foundations[idx - 1]
            cards_line = " ".join(str(c) for c in pile) if pile else "--"
            print(f"F{idx}: {cards_line}")

        # Tableau T1..T7
        for i, pile in enumerate(self.tableau, start=1):
            print(f"T{i}: {pile_to_str(pile)}")
        print()

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

    def find_foundation_dest_for_card(self, card: Card) -> Optional[int]:
        """Find a foundation pile index that can accept the card, if any."""
        # If not an Ace, it must continue a pile of the same suit
        if card.rank != 1:
            for i, pile in enumerate(self.foundations):
                if (
                    pile
                    and pile[-1].suit == card.suit
                    and pile[-1].rank + 1 == card.rank
                ):
                    return i
            return None
        # Ace: can go to any empty foundation
        for i, pile in enumerate(self.foundations):
            if not pile:
                return i
        return None

    def can_move_to_foundation(self, card: Card) -> bool:
        """Check if the card can be moved to any foundation pile."""
        return self.find_foundation_dest_for_card(card) is not None

    def move_from_waste_to_foundation(self) -> bool:
        """Attempt to move the top waste card to any valid foundation. Returns True if moved."""
        if not self.waste:
            return False
        card, _ = self.waste[-1]
        dest = self.find_foundation_dest_for_card(card)
        if dest is None:
            return False
        self.waste.pop()
        self.foundations[dest].append(card)
        return True

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

    def move_from_tableau_to_foundation(self, pile_index: int) -> bool:
        """Attempt to move the top card of the specified tableau pile to any foundation."""
        if not (0 <= pile_index < len(self.tableau)):
            return False
        pile = self.tableau[pile_index]
        if not pile:
            return False
        card, face_up = pile[-1]
        if not face_up:
            return False
        dest = self.find_foundation_dest_for_card(card)
        if dest is None:
            return False
        pile.pop()
        self.foundations[dest].append(card)
        # flip next card if it was face down
        if pile and not pile[-1][1]:
            c, _ = pile[-1]
            pile[-1] = (c, True)
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

    def auto_play(self, verbose: bool = False) -> bool:
        """
        Attempt to automatically play using a simple greedy strategy with cycle detection.
        Returns True if won, False if stuck.
        """

        # Create a stable, hashable representation of the full game state
        def state_key() -> Tuple:
            def card_id(c: Card) -> str:
                return f"{c.rank}{c.suit}"

            tableau_key = tuple(
                tuple((card_id(c), up) for c, up in pile) for pile in self.tableau
            )
            foundations_key = tuple(
                tuple(card_id(c) for c in pile) for pile in self.foundations
            )
            stock_key = tuple(card_id(c) for c, _ in self.stock)
            waste_key = tuple(card_id(c) for c, _ in self.waste)
            return (tableau_key, foundations_key, stock_key, waste_key, self.draw_count)

        def apply_all_greedy_moves() -> bool:
            any_progress = False

            def face_up_run_len(pile: List[Tuple[Card, bool]]) -> int:
                run = 0
                for card, up in reversed(pile):
                    if not up:
                        break
                    run += 1
                return run

            # 1) Prefer tableau -> tableau moves that expose a face-down card
            for src_index in range(7):
                src_pile = self.tableau[src_index]
                run = face_up_run_len(src_pile)
                if run == 0:
                    continue
                exposes = len(src_pile) > run and not src_pile[-run - 1][1]
                if not exposes:
                    continue
                # Try moving minimal sub-sequence that still exposes (i.e., move exactly run cards)
                count = run
                for dest_index in range(7):
                    if src_index == dest_index:
                        continue
                    if self.move_tableau_to_tableau(src_index, count, dest_index):
                        return True

            # 2) Other tableau -> tableau moves (small to large counts)
            for src_index in range(7):
                src_pile = self.tableau[src_index]
                count = 1
                while count <= len(src_pile) and (
                    len(src_pile) > 0 and src_pile[-count][1]
                ):
                    for dest_index in range(7):
                        if src_index == dest_index:
                            continue
                        if self.move_tableau_to_tableau(src_index, count, dest_index):
                            return True
                    count += 1

            # Helper to decide if moving to foundation is safe enough (very simple heuristic):
            # Only move to foundation if the card cannot currently be placed on any tableau pile.
            def safe_to_foundation(card: Card) -> bool:
                for dest_pile in self.tableau:
                    dest_top = dest_pile[-1][0] if dest_pile else None
                    if self.can_place_on_tableau(dest_top, card):
                        return False
                return True

            # 3) Waste -> tableau preferred over foundation
            if self.waste:
                wcard, _ = self.waste[-1]
                for dest_index in range(7):
                    dest_pile = self.tableau[dest_index]
                    dest_top = dest_pile[-1][0] if dest_pile else None
                    if self.can_place_on_tableau(dest_top, wcard):
                        if self.move_waste_to_tableau(dest_index):
                            return True

            # 4) Tableau -> foundation if safe
            moved = True
            while moved:
                moved = False
                for i in range(7):
                    pile = self.tableau[i]
                    if not pile or not pile[-1][1]:
                        continue
                    card = pile[-1][0]
                    if self.can_move_to_foundation(card) and safe_to_foundation(card):
                        if self.move_from_tableau_to_foundation(i):
                            moved = True
                            any_progress = True

            # 5) Waste -> foundation if safe
            if self.waste:
                wcard, _ = self.waste[-1]
                if self.can_move_to_foundation(wcard) and safe_to_foundation(wcard):
                    if self.move_from_waste_to_foundation():
                        any_progress = True
                        return True

            return any_progress

        draws_without_progress = 0
        seen_counts: Dict[Tuple, int] = {}
        total_steps = 0
        max_total_steps = 200000

        # Use a conservative cap for draws without making any other move: full cycle + buffer
        def max_draws_in_cycle() -> int:
            total = len(self.stock) + len(self.waste)
            if self.draw_count <= 0:
                return 0
            # ceil(total / draw_count) + 1 buffer
            return (total + self.draw_count - 1) // self.draw_count + 1

        while True:
            total_steps += 1
            if total_steps > max_total_steps:
                if verbose:
                    print("Stopping due to step limit; likely stuck.")
                return False

            key = state_key()
            cnt = seen_counts.get(key, 0) + 1
            seen_counts[key] = cnt
            if cnt > 2:  # seen the exact same state more than twice -> loop
                if verbose:
                    print("Detected repeating state; stopping auto-play as stuck.")
                return False
            if self.is_won():
                if verbose:
                    print("Game won by auto-play!")
                return True

            if apply_all_greedy_moves():
                draws_without_progress = 0
                continue

            # No moves possible; attempt to draw
            if not self.draw():
                # Cannot draw and no moves -> stuck
                if verbose:
                    print("Auto-play could not win the game.")
                return False

            draws_without_progress += 1
            if draws_without_progress > max_draws_in_cycle():
                # We've cycled through the stock without progress -> stuck
                if verbose:
                    print("Auto-play could not win the game.")
                return False

    def interactive_play(self) -> None:
        """
        Play the game interactively via terminal inputs with simplified commands:
        - draw: draw from the stock to the waste
        - move <src> <dst> [count]: move cards between piles

        Piles:
        - Stock is implicit for draw.
        - Waste is 'W'.
        - Foundations are 'F1'..'F4' (♣️, ♦️, ♥️, ♠️).
        - Tableau are 'T1'..'T7'.
        """
        print("Welcome to Klondike Solitaire. Type 'help' for available commands.")

        def parse_pile(token: str) -> Tuple[str, Optional[int]]:
            token = token.upper()
            if token == "W":
                return ("W", None)
            if token.startswith("T") and token[1:].isdigit():
                idx = int(token[1:])
                if 1 <= idx <= 7:
                    return ("T", idx - 1)
            if token.startswith("F") and token[1:].isdigit():
                idx = int(token[1:])
                if 1 <= idx <= 4:
                    return ("F", idx - 1)
            return ("?", None)

        while True:
            self.print_board()
            if self.is_won():
                print("Congratulations! You've won the game.")
                break
            command = input("Enter command: ").strip()
            if not command:
                continue
            parts = command.split()
            op = parts[0].lower()
            if op == "draw":
                if not self.draw():
                    print("Cannot draw. Both stock and waste are empty.")
                continue

            if op == "move":
                if len(parts) not in (3, 4):
                    print("Usage: move <src> <dst> [count]")
                    continue
                src_t, src_i = parse_pile(parts[1])
                dst_t, dst_i = parse_pile(parts[2])
                count = 1
                if len(parts) == 4:
                    if parts[3].lower() == "all":
                        count = -1  # sentinel for "all face-up"
                    else:
                        try:
                            count = int(parts[3])
                        except ValueError:
                            print("Invalid count. Use a number or 'all'.")
                            continue
                        if count <= 0:
                            print("Count must be positive.")
                            continue

                if src_t == "?" or dst_t == "?":
                    print("Invalid pile. Use W, F1..F4, or T1..T7.")
                    continue

                moved = False
                # Moves to Foundations
                if dst_t == "F":
                    if src_t == "W":
                        if count != 1:
                            print("Can only move 1 card from waste to foundation.")
                        else:
                            if not self.waste:
                                moved = False
                            else:
                                moved = self.move_from_waste_to_foundation_at(dst_i)
                    elif src_t == "T":
                        if count != 1:
                            print("Can only move 1 card to foundation.")
                        else:
                            pile = self.tableau[src_i]
                            if not pile or not pile[-1][1]:
                                moved = False
                            else:
                                moved = self.move_from_tableau_to_foundation_at(
                                    src_i, dst_i
                                )
                    else:
                        print("Unsupported move to foundation from that source.")

                # Moves to Tableau
                elif dst_t == "T":
                    if src_t == "W":
                        if count != 1:
                            print("Can only move 1 card from waste to tableau.")
                        else:
                            moved = self.move_waste_to_tableau(dst_i)
                    elif src_t == "T":
                        if count == -1:
                            # move the entire face-up portion
                            src_pile = self.tableau[src_i]
                            run = 0
                            for c, up in reversed(src_pile):
                                if not up:
                                    break
                                run += 1
                            if run <= 0:
                                moved = False
                            else:
                                moved = self.move_tableau_to_tableau(src_i, run, dst_i)
                        else:
                            moved = self.move_tableau_to_tableau(src_i, count, dst_i)
                    elif src_t == "F":
                        if count != 1:
                            print("Can only move 1 card from foundation to tableau.")
                        else:
                            foundation_pile = self.foundations[src_i]
                            if not foundation_pile:
                                moved = False
                            else:
                                card = foundation_pile[-1]
                                dest_pile = self.tableau[dst_i]
                                dest_top_card = dest_pile[-1][0] if dest_pile else None
                                if self.can_place_on_tableau(dest_top_card, card):
                                    foundation_pile.pop()
                                    dest_pile.append((card, True))
                                    moved = True
                                else:
                                    moved = False
                    else:
                        print("Unsupported move to tableau from that source.")

                else:
                    print("Cannot move to waste or stock directly.")

                if not moved:
                    print("Invalid move.")
                continue

            if op == "auto":
                print("Attempting to auto-solve...")
                if self.auto_play(verbose=True):
                    print("Auto-solver won the game!")
                else:
                    print("Auto-solver could not solve the game.")
                if self.is_won():
                    break
                continue

            if op == "help":
                print("Commands:")
                print(" draw                 : Draw a card from the stock to the waste")
                print(" move <src> <dst> [n] : Move n (default 1) cards between piles")
                print(
                    "                         src/dst: W, F1..F4, T1..T7; use 'all' for n to move all face-up in a tableau"
                )
                print(" auto                 : Attempt an automatic solution")
                print(" help                 : Display this help message")
                print(" quit                 : Exit the game")
                continue

            if op in ("quit", "q", "exit"):
                print("Exiting game.")
                break

            print("Unknown command. Type 'help' for available commands.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Play a game of Klondike solitaire in the terminal."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for random shuffling (for reproducible games)",
    )
    parser.add_argument(
        "--draw_count",
        type=int,
        default=3,
        choices=[1, 3],
        help="Number of cards to draw from stock (1 or 3)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatically play the game without interaction",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print board state during auto-play"
    )
    args = parser.parse_args()
    game = KlondikeGame(seed=args.seed, draw_count=args.draw_count)
    if args.auto:
        won = game.auto_play(verbose=args.verbose)
        if won:
            print("Auto-play result: Win!")
        else:
            print("Auto-play result: Loss.")
    else:
        game.interactive_play()


if __name__ == "__main__":
    main()
