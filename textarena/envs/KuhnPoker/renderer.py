from typing import Any, Dict, Optional

def create_board_str(game_state: Dict[str, Any], viewer_id: Optional[int] = None) -> str:
    def rank_to_str(rank: int) -> str: return {0: 'J', 1: 'Q', 2: 'K'}.get(rank, '?')
    pot = game_state.get("pot", 0)
    player_chips = game_state.get("player_chips", {0: 0, 1: 0})
    current_round = game_state.get("current_round", 1)
    cards = game_state.get("player_cards", {0: None, 1: None})
    p0_card = rank_to_str(cards.get(0)) if viewer_id == 0 else "?"
    p1_card = rank_to_str(cards.get(1)) if viewer_id == 1 else "?"
    p0_chips = f"{player_chips.get(0, 0):>3}"; p1_chips = f"{player_chips.get(1, 0):>3}"
    board_str = f"""
┌────────────────────────┐
│ Round: {current_round:<3}  Pot:   {pot:<3} │
└────────────────────────┘

┌── P0 ({p0_chips}$) ──┐    ┌── P1 ({p1_chips}$) ──┐
│               │    │               │
│  ┌─────────┐  │    │  ┌─────────┐  │
│  │ {p0_card}       │  │    │  │ {p1_card}       │  │
│  │         │  │    │  │         │  │
│  │    ♥    │  │    │  │    ♠    │  │
│  │         │  │    │  │         │  │
│  │       {p0_card} │  │    │  │       {p1_card} │  │
│  └─────────┘  │    │  └─────────┘  │
│               │    │               │
└───────────────┘    └───────────────┘
""".strip()
    return board_str