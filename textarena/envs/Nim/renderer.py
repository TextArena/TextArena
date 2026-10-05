from typing import List


MAX_RENDERED_TOKENS = 50


def create_board_str(piles: List[int]) -> str:
    max_tokens = max(piles) if piles else 0
    if max_tokens == 0:
        return "\n".join(f"Pile {i}: (empty)" for i in range(len(piles)))
    visible_width = min(max_tokens, MAX_RENDERED_TOKENS)
    lines = []
    for i, count in enumerate(piles):  # Each row
        token_cells = [f"│ {'●' if j < count else ' '}" for j in range(visible_width)]
        token_row = " ".join(token_cells) + " │"
        if count > MAX_RENDERED_TOKENS:
            token_row += f" … ({count} total)"
        border_row = "       " + "└───" * visible_width + "┘"
        lines.append(f"Pile {i}: {token_row}")
        lines.append(border_row + "\n")
    return "\n".join(lines).rstrip()
