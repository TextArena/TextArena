"""A minimal script showing how to run TextArena Avalon locally with DeepRole + Tinker."""

import os
import sys
from pathlib import Path

# Prefer this repo's `textarena/` package over any site-packages install (PyPI builds omit Avalon-v0).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import textarena as ta  # noqa: E402


def _load_env_file(path: Path) -> None:
    """Set os.environ from KEY=value lines (stdlib only; does not override existing vars)."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


_env_file = _REPO_ROOT / ".env"
_load_env_file(_env_file)

# Tinker (OpenAI-compatible): https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/
if not os.getenv("TINKER_API_KEY"):
    raise SystemExit(
        "TINKER_API_KEY is not set after loading:\n"
        f"  {_env_file}\n"
        "Add TINKER_API_KEY=... and TINKER_MODEL (sampler weight path) to that file, "
        "or export them in your shell."
    )

tinker_model = os.getenv("TINKER_MODEL")
if not tinker_model:
    raise SystemExit(
        "TINKER_MODEL is not set. Set it to your Tinker sampler path, e.g.\n"
        "  TINKER_MODEL=tinker://UUID:train:0/sampler_weights/000080\n"
        "See https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/"
    )

# Faster turns: shared Tinker client, lighter CFR defaults, skip LLM on mechanical phases.
_dr_kw = dict(
    llm_provider="tinker",
    model=tinker_model,
    fast_deeprole=True,
    share_llm_backend=True,
    skip_llm_for_mechanical=True,
)

agents = {
    0: ta.agents.DeepRole_LLM(**_dr_kw),
    1: ta.agents.DeepRole_LLM(**_dr_kw),
    2: ta.agents.DeepRole_LLM(**_dr_kw),
    3: ta.agents.DeepRole_LLM(**_dr_kw),
    4: ta.agents.DeepRole_LLM(**_dr_kw),
}

# initialize the environment (Merlin + Morgana + 2 Servants + 1 Minion at 5p; enables guess-Merlin phase)
_AVALON_SPECIAL_ROLES = {"Merlin", "Morgana"}
env = ta.make(env_id="Avalon-v0")
env.reset(num_players=len(agents), special_roles=_AVALON_SPECIAL_ROLES)

# main game loop
done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action=action)
rewards, game_info = env.close()

print(f"Rewards: {rewards}")
print(f"Game Info: {game_info}")
