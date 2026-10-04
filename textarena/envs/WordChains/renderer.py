from typing import Dict, Any

def create_board_str(game_state: Dict[str, Any]) -> str:
    current_word = game_state["current_word"]
    required_start = game_state["required_start_letter"]
    required_length = game_state["required_length"]
    used_words = sorted(game_state["used_words"], key=lambda word: (len(word), word))

    max_width = max(len(word) for word in used_words + [current_word])
    border = "+" + "-" * (max_width + 26) + "+"

    lines = [border]
    lines.append(f"| Current Word        : {current_word:<{max_width}}   |")
    lines.append(f"| Required Start      : '{required_start}'{' ' * (max_width - 1)} |")
    lines.append(f"| Required Length     : {required_length:<{max_width}}   |")
    lines.append(border)
    sp = " "
    lines.append(f"| Used Words ({len(used_words):<2} total):"+f"{sp:<{max_width}}"+"   |")
    for word in used_words:
        lines.append(f"|   - {word:<{max_width+20}} |")
    lines.append(border)

    return "\n".join(lines)
