from typing import List, Optional, Tuple

def create_board_str(board: List[List[Tuple[int, Optional[Tuple[int, int]]]]]) -> str:
    """
    Renders the Santorini board using ASCII art with clear separation of building height and worker.
    
    Args:
        board: 5x5 grid where each cell contains (height, worker):
              - height: 0-3 for levels, 4 for dome
              - worker: None or (player_id, worker_num)
    
    Returns:
        String representation of the board where each cell shows:
        [H|W] format where:
        - H: Building height (0-3) or 4 for dome
        - W: Worker symbol or empty space
    """
    # Map pieces to symbols
    # Worker symbols for each player
    WORKER_SYMBOLS = {
        0: ["N1", "N2"],  # Navy
        1: ["W1", "W2"],  # White
        2: ["G1", "G2"]   # Grey
    }
    
    # Create a dictionary for all squares
    squares = {}
    for row in range(5):
        for col in range(5):
            height, worker = board[row][col]
            
            # Get height symbol
            if height == 4:  # Dome
                height_symbol = "4"
            else:
                height_symbol = str(height)
            
            # Get worker symbol
            if worker is None:
                worker_symbol = "  "
            else:
                player_id, worker_num = worker
                worker_symbol = WORKER_SYMBOLS[player_id][worker_num - 1]
            
            # Format cell with fixed width and consistent spacing
            squares[f"{chr(65+row)}{col+1}"] = f"{height_symbol} {worker_symbol}"

    # Board template with fixed-width cells and proper alignment
    board_template = """
     1     2     3     4     5
  ┌─────┬─────┬─────┬─────┬─────┐
A │ {A1}│ {A2}│ {A3}│ {A4}│ {A5}│ A
  ├─────┼─────┼─────┼─────┼─────┤
B │ {B1}│ {B2}│ {B3}│ {B4}│ {B5}│ B
  ├─────┼─────┼─────┼─────┼─────┤
C │ {C1}│ {C2}│ {C3}│ {C4}│ {C5}│ C
  ├─────┼─────┼─────┼─────┼─────┤
D │ {D1}│ {D2}│ {D3}│ {D4}│ {D5}│ D
  ├─────┼─────┼─────┼─────┼─────┤
E │ {E1}│ {E2}│ {E3}│ {E4}│ {E5}│ E
  └─────┴─────┴─────┴─────┴─────┘
     1     2     3     4     5

Legend:
- Cell format is [height worker]
- Height: 0-3 for building levels, 4 for dome
- Workers: Navy(N1,N2), White(W1,W2), Grey(G1,G2)
"""
    
    return board_template.format(**squares)
