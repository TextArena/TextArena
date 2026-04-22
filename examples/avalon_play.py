"""Run TextArena Avalon locally with five DeepRole-LLM agents backed by a
TRL-trained (or any HuggingFace) model.

Quick start
-----------
1. Install dependencies:
       pip install textarena transformers torch peft bitsandbytes

2. Set the model in .env (or export in your shell):
       HF_MODEL=Qwen/Qwen3-0.6B          # HF Hub name  (downloaded on first run)
       # -- OR --
       HF_MODEL=/checkpoints/my-grpo-run/checkpoint-500   # local TRL checkpoint

   Optional PEFT/LoRA adapter produced by TRL:
       ADAPTER_PATH=/checkpoints/my-lora-adapter

   Optional quantisation to reduce VRAM (pick one):
       LOAD_IN_4BIT=1    # QLoRA  (takes priority)
       LOAD_IN_8BIT=1    # 8-bit bitsandbytes

3. Run:
       python avalon_play.py
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
# Resolve model settings from environment
# ---------------------------------------------------------------------------

model_name_or_path = os.getenv("HF_MODEL")
if not model_name_or_path:
    raise SystemExit(
        "HF_MODEL is not set.\n"
        "Set it to a HuggingFace Hub name or local checkpoint path, e.g.:\n"
        "  HF_MODEL=Qwen/Qwen3-0.6B\n"
        "  HF_MODEL=/checkpoints/my-grpo-run/checkpoint-500\n"
        "Add it to .env or export it in your shell."
    )

adapter_path  = os.getenv("ADAPTER_PATH") or None   # optional PEFT/LoRA adapter
load_in_4bit  = os.getenv("LOAD_IN_4BIT",  "0").strip() not in ("0", "", "false", "False")
load_in_8bit  = os.getenv("LOAD_IN_8BIT",  "0").strip() not in ("0", "", "false", "False")

# ---------------------------------------------------------------------------
# Build agents
# ---------------------------------------------------------------------------

# All five players share the same loaded model weights (share_llm_backend=True
# avoids loading the checkpoint into GPU memory five separate times).
# skip_llm_for_mechanical=True means the LLM is only called on discussion
# turns; DeepRole handles vote/propose/mission mechanically, saving inference.
_agent_kwargs = dict(
    model_name_or_path     = model_name_or_path,
    adapter_path           = adapter_path,
    load_in_4bit           = load_in_4bit,
    load_in_8bit           = load_in_8bit,
    fast_deeprole          = True,
    share_llm_backend      = True,
    skip_llm_for_mechanical= True,
)

agents = {i: ta.agents.DeepRole_LLM(**_agent_kwargs) for i in range(5)}

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