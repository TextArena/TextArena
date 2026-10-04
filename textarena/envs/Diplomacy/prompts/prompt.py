
from pathlib import Path


_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(filename: str) -> str:
    """Helper to load prompt text from file"""
    return (_PROMPTS_DIR / filename).read_text().strip()

def get_state_specific_prompt(state: str) -> str:
    return load_prompt(f"state_specific/{state.lower()}_system_prompt.txt")





