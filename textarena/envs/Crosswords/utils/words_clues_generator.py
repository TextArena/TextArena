import argparse
import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Union

from nltk.corpus import words


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "words_clues.jsonl"


def get_clue_examples(word: str, model: str = "gpt-4o-mini") -> Dict[str, str]:
    """
    Get 10 clue examples for the specified word from OpenRouter.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY must be set to generate crossword clues")

    # Keep the network client lazy so importing the helper (including
    # ``--help`` and offline tests) never requires credentials or network.
    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": (
                    "I am getting clues that will be used for the game 'crosswords'. "
                    f"Provide 10 distinct clue sentences for the word '{word}', each "
                    "on its own line without numbering. Include the number of letters "
                    "at the end of each clue, e.g. (5 letters)."
                ),
            }
        ],
        temperature=0.7,
    )
    content = response.choices[0].message.content
    clues: List[str] = [line.strip() for line in (content or "").splitlines() if line.strip()]
    if len(clues) < 10:
        raise RuntimeError(f"OpenRouter returned only {len(clues)} clues for {word!r}")
    return {str(index): clue for index, clue in enumerate(clues[:10], start=1)}


def _usable_words(corpus_name: str) -> List[str]:
    try:
        corpus = words.words(corpus_name)
    except LookupError as exc:
        raise RuntimeError(
            "The NLTK words corpus is required; install it with nltk.download('words')."
        ) from exc
    return list(dict.fromkeys(word.lower() for word in corpus if word.isalpha()))


def main(
    num_words: int = 10,
    output_path: Optional[Union[str, Path]] = None,
    seed: Optional[int] = None,
    model: str = "gpt-4o-mini",
) -> Path:
    if not isinstance(num_words, int) or isinstance(num_words, bool) or num_words < 1:
        raise ValueError("num_words must be a positive integer")

    rng = random.Random(seed)
    easy_pool = _usable_words("en-basic")
    hard_pool = _usable_words("en")
    if len(easy_pool) < num_words or len(hard_pool) < num_words:
        raise ValueError("requested more words than the NLTK corpus provides")

    selected = [
        *((word, False) for word in rng.sample(easy_pool, num_words)),
        *((word, True) for word in rng.sample(hard_pool, num_words)),
    ]
    entries = []
    for word, hardcore in selected:
        clues = get_clue_examples(word, model=model)
        if not clues or not all(isinstance(clue, str) and clue for clue in clues.values()):
            raise RuntimeError(f"invalid clues generated for {word!r}")
        entries.append({"word": word, "hardcore": hardcore, "clues": clues})

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file:
            for entry in entries:
                file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a crossword dataset.")
    parser.add_argument("--num-words", type=int, default=10, help="Words per difficulty.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()
    generated_path = main(args.num_words, args.output, args.seed, args.model)
    print(f"Dataset generated at {generated_path}")
