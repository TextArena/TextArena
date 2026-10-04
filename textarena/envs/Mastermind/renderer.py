from typing import Dict, Any, List

def create_board_str(
    game_state: Dict[str, Any],
    reveal_secret: bool = False,
) -> str:
    secret_code = game_state.get("secret_code", [])
    history: List[Dict[str, Any]] = game_state.get("history", [])
    def format_code(code):
        return " ".join(f"[{num}]" for num in code)
    def format_feedback(b: int, w: int) -> str:
        return f"{' 🎯' * b}{' ⚪' * w}{' ▫️' * (len(secret_code) - b - w)}"
    lines = [
        "===============================================================",
        (
            f"Secret Code: {format_code(secret_code)}"
            if reveal_secret
            else f"Secret Code: {' '.join('[?]' for _ in secret_code)}"
        ),
        "===============================================================",
    ]
    if not history:
        lines.append("No guesses yet.")
    else:
        lines.append("📜 Guess History:")
        for i, item in enumerate(history, 1):
            guess = format_code(item["guess"])
            feedback = format_feedback(item["black"], item["white"])
            lines.append(f"{i:2}. Guess: {guess}   Feedback: {feedback}")
    return "\n".join(lines)
