from typing import Optional

from textarena.envs.Chess.board import Board, parse_square

def create_board_str(board: Board, player_id: Optional[int] = None) -> str:
    piece_symbols = {'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟', 'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙'}
    squares = {}
    for file_char in "abcdefgh":
        for rank_char in "12345678":
            square_name = f"{file_char}{rank_char}"
            piece = board.piece_at(parse_square(square_name))
            squares[square_name] = piece_symbols[piece.symbol()] if piece else " "

    board_template = f"""
    a    b    c    d    e    f    g    h  
  ┌────┬────┬────┬────┬────┬────┬────┬────┐
8 │ {{a8}}  │ {{b8}}  │ {{c8}}  │ {{d8}}  │ {{e8}}  │ {{f8}}  │ {{g8}}  │ {{h8}}  │ 8
  ├────┼────┼────┼────┼────┼────┼────┼────┤
7 │ {{a7}}  │ {{b7}}  │ {{c7}}  │ {{d7}}  │ {{e7}}  │ {{f7}}  │ {{g7}}  │ {{h7}}  │ 7
  ├────┼────┼────┼────┼────┼────┼────┼────┤
6 │ {{a6}}  │ {{b6}}  │ {{c6}}  │ {{d6}}  │ {{e6}}  │ {{f6}}  │ {{g6}}  │ {{h6}}  │ 6
  ├────┼────┼────┼────┼────┼────┼────┼────┤
5 │ {{a5}}  │ {{b5}}  │ {{c5}}  │ {{d5}}  │ {{e5}}  │ {{f5}}  │ {{g5}}  │ {{h5}}  │ 5
  ├────┼────┼────┼────┼────┼────┼────┼────┤
4 │ {{a4}}  │ {{b4}}  │ {{c4}}  │ {{d4}}  │ {{e4}}  │ {{f4}}  │ {{g4}}  │ {{h4}}  │ 4
  ├────┼────┼────┼────┼────┼────┼────┼────┤
3 │ {{a3}}  │ {{b3}}  │ {{c3}}  │ {{d3}}  │ {{e3}}  │ {{f3}}  │ {{g3}}  │ {{h3}}  │ 3
  ├────┼────┼────┼────┼────┼────┼────┼────┤
2 │ {{a2}}  │ {{b2}}  │ {{c2}}  │ {{d2}}  │ {{e2}}  │ {{f2}}  │ {{g2}}  │ {{h2}}  │ 2
  ├────┼────┼────┼────┼────┼────┼────┼────┤
1 │ {{a1}}  │ {{b1}}  │ {{c1}}  │ {{d1}}  │ {{e1}}  │ {{f1}}  │ {{g1}}  │ {{h1}}  │ 1
  └────┴────┴────┴────┴────┴────┴────┴────┘
    a    b    c    d    e    f    g    h
"""
    return board_template.format(**squares)


