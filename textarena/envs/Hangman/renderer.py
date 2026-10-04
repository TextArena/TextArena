from typing import Dict, Any


def create_board_str(game_state: Dict[str, Any], reveal_answer: bool = False) -> str:
    """ Render the Hangman board showing the current guessed word and a hangman drawing based on tries left """
    # Hangman ASCII art (indexed by remaining tries: 6 down to 0)
    hangman_stages = [
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            r" |      /|\   ",
            r" |      / \   ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            r" |      /|\   ",
            " |      /     ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            r" |      /|\   ",
            " |            ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            " |      /|    ",
            " |            ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            " |       |    ",
            " |            ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |      (X)   ",
            " |            ",
            " |            ",
            " |            ",
            "_|___         "
        ],
        [
            "  _______     ",
            " |/      |    ",
            " |            ",
            " |            ",
            " |            ",
            " |            ",
            "_|___         "
        ],
    ]

    tries_left = max(0, min(6, game_state["tries_left"]))
    hangman_drawing = hangman_stages[tries_left]
    board = " ".join(game_state.get("current_board", []))
    guessed_letters = ", ".join(sorted(game_state.get("guessed_letters", set()))) or "none"
    guessed_words = ", ".join(sorted(game_state.get("guessed_words", set()))) or "none"
    answer = f"\n🎯 Answer: {game_state['target_word'].upper()}" if reveal_answer else ""

    return (
        f"🎯 Word: {board}\n\n"
        + "\n".join(hangman_drawing)
        + f"\n\n❤️ Tries left: {game_state['tries_left']}"
        + f"\n🔤 Guessed letters: {guessed_letters}"
        + f"\n📝 Guessed words: {guessed_words}"
        + answer
    )