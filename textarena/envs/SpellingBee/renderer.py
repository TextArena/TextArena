def create_board_str(game_state: dict) -> str:
    allowed_letters = sorted(game_state.get("allowed_letters", []))
    def render_allowed_letters_lines():
        lines = []
        lines.append("┌─ ALLOWED LETTERS ──────────────────┐")
        lines.append("│                                    │")
        rows = [allowed_letters[i:i + 6] for i in range(0, len(allowed_letters), 6)]
        if not rows:
            rows = [[]]
        for row in rows:
            line_top = "".join("┌───┐ " for _ in row).rstrip()
            line_mid = "".join(f"│ {ch.upper()} │ " for ch in row).rstrip()
            line_bot = "".join("└───┘ " for _ in row).rstrip()
            for content in (line_top, line_mid, line_bot):
                left = (36 - len(content)) // 2
                right = 36 - len(content) - left
                lines.append(f"│{' ' * left}{content}{' ' * right}│")
            lines.append("│                                    │")
        lines.append("└────────────────────────────────────┘")
        return lines
    def render_word_history_lines():
        lines = []
        lines.append("┌─ GAME HISTORY ───────────────────┐")
        lines.append("│                                  │")
        for i, word in enumerate(game_state.get("word_history", [])):
            player = f"P{i % 2}"
            entry = f"{player}: {word.upper()} ({len(word):<2} letters)   "
            lines.append(f"│  {entry[:32].ljust(32)}│")
        lines.append("│                                  │")
        lines.append("└──────────────────────────────────┘")
        return lines
    left_box = render_allowed_letters_lines()
    right_box = render_word_history_lines()
    max_lines = max(len(left_box), len(right_box))
    left_box += [" " * len(left_box[0])] * (max_lines - len(left_box))
    right_box += [" " * len(right_box[0])] * (max_lines - len(right_box))
    combined = [f"{l:<50} {r}" for l, r in zip(left_box, right_box)]
    return "\n".join(combined)
