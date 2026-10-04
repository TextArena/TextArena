from typing import List

def create_board_str(board: List[List[int]]) -> str:
    def cell_str(num):
        return str(num) if num != 0 else " "

    col_header = "    " + "   ".join([str(i) if i % 3 != 0 else f"{i}  " for i in range(1, 10)])
    thick_line =     "  ┌───┬───┬───┐ ┌───┬───┬───┐ ┌───┬───┬───┐"
    mid_thin_line =  "  ├───┼───┼───┤ ├───┼───┼───┤ ├───┼───┼───┤"
    bottom_line =    "  └───┴───┴───┘ └───┴───┴───┘ └───┴───┴───┘"
    lines = [col_header, thick_line]

    for i in range(9):
        row = board[i]
        row_label = str(i + 1)
        row_line = f"{row_label}"
        for j in range(9):
            val = cell_str(row[j])
            row_line += f" {val} │"  if (j) % 3 != 0 else f" │ {val} │"
        row_line += f" {row_label}"
        lines.append(row_line)

        if i<8:
            if (i-2)%3 == 0:
                lines.append(bottom_line) 
                lines.append(thick_line) 
            else:
                lines.append(mid_thin_line)

    lines.append(bottom_line)
    lines.append(col_header)
    return "\n".join(lines)
