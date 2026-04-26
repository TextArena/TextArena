"""Run TextArena Avalon locally with five TinkerDistilAgent players backed
by a Tinker-hosted LoRA checkpoint (typically one produced by
``tinker_multiagent.py``).

Quick start
-----------
1. Install dependencies:
       pip install textarena openai

2. Set the Tinker config in .env (or export in your shell):
       TINKER_API_KEY=<your-key>
       TINKER_MODEL=tinker://UUID:train:0/sampler_weights/000080

   The TINKER_MODEL value is logged by tinker_multiagent.py at every
   checkpoint — pick one from results/tinker_avalon/<run>/checkpoints.jsonl.

3. Run:
       python avalon_play_tinker.py
"""

import os
import sys
from pathlib import Path

# Prefer this repo's textarena/ package over any site-packages install
# (PyPI builds omit Avalon-v0).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import textarena as ta  # noqa: E402


# ---------------------------------------------------------------------------
# .env loader (stdlib only — no python-dotenv required)
# ---------------------------------------------------------------------------

def _load_env_file(path: Path) -> None:
    """Set os.environ from KEY=value lines; does not override existing vars."""
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


_load_env_file(_REPO_ROOT / ".env")


# ---------------------------------------------------------------------------
# Resolve Tinker settings from environment
# ---------------------------------------------------------------------------

if not os.getenv("TINKER_API_KEY"):
    raise SystemExit(
        "TINKER_API_KEY is not set.\n"
        "Get a key at https://tinker-docs.thinkingmachines.ai/tinker/quickstart/\n"
        "Add TINKER_API_KEY=... to .env or export it in your shell."
    )

tinker_model_path = os.getenv("TINKER_MODEL")
if not tinker_model_path:
    raise SystemExit(
        "TINKER_MODEL is not set.\n"
        "Set it to a Tinker sampler weight path, e.g.:\n"
        "  TINKER_MODEL=tinker://UUID:train:0/sampler_weights/000080\n"
        "Paths are logged by tinker_multiagent.py in checkpoints.jsonl."
    )

# ---------------------------------------------------------------------------
# Build agents
# ---------------------------------------------------------------------------
#
# All five players share the same Tinker checkpoint.  Unlike DeepRole_LLM,
# there's no local-weight sharing flag here — Tinker hosts the model and
# every call goes over the network, so a per-agent OpenAI client is
# sufficient (and is what TinkerDistilAgent's internal _TinkerSamplerBackend
# already provides; see textarena/agents/basic_agents.py).
#
# skip_llm_for_mechanical=True means the LLM is only called on discussion
# turns; DeepRole handles vote/propose/mission mechanically, saving inference
# tokens (and Tinker API quota).

_agent_kwargs = dict(
    tinker_model_path        = tinker_model_path,
    fast_deeprole            = True,
    skip_llm_for_mechanical  = True,
)

agents = {i: ta.agents.TinkerDistilAgent(**_agent_kwargs) for i in range(5)}

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_AVALON_SPECIAL_ROLES = {"Merlin", "Morgana"}
env = ta.make(env_id="Avalon-v0")
env.reset(num_players=len(agents), special_roles=_AVALON_SPECIAL_ROLES)

# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action=action)

rewards, game_info = env.close()

print(f"Rewards:   {rewards}")
print(f"Game Info: {game_info}")