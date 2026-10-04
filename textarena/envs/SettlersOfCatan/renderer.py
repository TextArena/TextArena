


RESOURCE_ORDER = ("brick", "wood", "wheat", "ore", "sheep")


def render_hand_cards_table(board, eliminated_pids=None, pids_from_roles=None) -> str:
    eliminated_pids = set(eliminated_pids or [])
    pids_from_roles = pids_from_roles or {}

    # Build table rows
    rows = []
    for color_enum, player in board.players.items():
        color_str = getattr(color_enum, "name", str(color_enum))
        pid = pids_from_roles.get(color_str.lower(), None)
        name = color_str + (" (eliminated)" if pid in eliminated_pids else "")
        counts = {k.name.lower(): v for k, v in player.hand.items()}
        row = [name] + [str(counts.get(r, 0)) for r in RESOURCE_ORDER]
        rows.append(row)
    headers = ["Player"] + [r.capitalize() for r in RESOURCE_ORDER]

    # Compute column widths
    widths = [max(len(headers[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(headers))]
    def sep_line() -> str: return "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    def fmt_row(values, right_align_idxs) -> str:
        cells = []
        for i, v in enumerate(values):
            if i in right_align_idxs:   cells.append(v.rjust(widths[i]))
            else:                       cells.append(v.ljust(widths[i]))
        return "| " + " | ".join(cells) + " |"

    # Assemble lines
    lines = ["Hand Cards", sep_line(), fmt_row(headers, right_align_idxs=set(range(1, len(headers)))), sep_line()]
    for row in rows: lines.append(fmt_row(row, right_align_idxs=set(range(1, len(headers)))))
    lines.append(sep_line())
    return "\n".join(lines)