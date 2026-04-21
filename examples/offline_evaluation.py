"""
In addition to evaluating your model online, here is a short example of how to
evaluate it offline against a fixed opponent.
We evaluate Groq's llama3-70b-8192 against a fixed opponent (Groq's mixtral-8x7b-32768).
"""
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from tqdm import tqdm

import textarena as ta

NUM_EPISODES = 8
EVAL_ENV_IDS = [("TicTacToe-v0", 2), ("Snake-v0", 4)]  # (env-id, num_players)
OPPONENT_NAME = "google/gemma-3-27b-it:free"
FILE_NAME = "eval_summary.csv"

# Model to evaluate
model = ta.agents.HFLocalAgent(
    model_name="Qwen/Qwen3-4B",
    max_new_tokens=512,
)

# Fixed opponent
opponent = ta.agents.OpenRouterAgent(model_name=OPPONENT_NAME)


def run_game(env_id: str, num_players: int, model, opponent) -> dict:
    """Play one episode and return per-episode stats for the *model* player."""
    env = ta.make(env_id)
    env.reset(num_players=num_players)

    model_pid = np.random.randint(0, num_players)    # random seat
    done = False

    while not done:
        pid, obs = env.get_observation()
        action = model(obs) if pid == model_pid else opponent(obs)
        done, _ = env.step(action=action)

    rewards, game_info = env.close()

    return {
        "model_reward": rewards[model_pid],
        "opponent_reward": np.mean([rewards[i] for i in range(num_players) if i != model_pid]),
        "invalid_move": bool(game_info[model_pid]["invalid_move"]),
        "turn_count":  game_info[model_pid]["turn_count"],
    }


results = defaultdict(list)

outer_bar = tqdm(EVAL_ENV_IDS, desc="Environments")
for env_id, num_players in outer_bar:

    # per-environment aggregates
    stats = dict(
        wins=0,
        losses=0,
        draws=0,
        total_reward_model=0.0,
        total_reward_opponent=0.0,
        total_invalid_moves=0,
        total_turns=0,
    )

    inner_bar = tqdm(range(NUM_EPISODES), desc=f"Evaluating {env_id}", leave=False)
    for _ in inner_bar:
        outcome = run_game(env_id, num_players, model, opponent)

        # W/L/D
        if outcome["model_reward"] > outcome["opponent_reward"]:
            stats["wins"] += 1
        elif outcome["model_reward"] < outcome["opponent_reward"]:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

        # Accumulate metrics
        stats["total_reward_model"]     += outcome["model_reward"]
        stats["total_reward_opponent"]  += outcome["opponent_reward"]
        stats["total_invalid_moves"]    += int(outcome["invalid_move"])
        stats["total_turns"]            += outcome["turn_count"]

        # Live progress bar
        games_done = _ + 1
        inner_bar.set_postfix({
            "Win%":   f"{stats['wins']   / games_done:.1%}",
            "Loss%":  f"{stats['losses'] / games_done:.1%}",
            "Draw%":  f"{stats['draws']  / games_done:.1%}",
            "Inv%":   f"{stats['total_invalid_moves'] / games_done:.1%}",
            "Turns":  f"{stats['total_turns'] / games_done:.1f}",
        })

    # write per-environment summary
    results["env_id"].append(env_id)
    results["win_rate"].append(stats["wins"] / NUM_EPISODES)
    results["loss_rate"].append(stats["losses"] / NUM_EPISODES)
    results["draw_rate"].append(stats["draws"] / NUM_EPISODES)
    results["invalid_rate"].append(stats["total_invalid_moves"] / NUM_EPISODES)
    results["avg_turns"].append(stats["total_turns"] / NUM_EPISODES)
    results["avg_model_reward"].append(stats["total_reward_model"] / NUM_EPISODES)
    results["avg_opponent_reward"].append(stats["total_reward_opponent"] / NUM_EPISODES)

df = pd.DataFrame(results)

# Pretty-print to console (Markdown table looks nice in most terminals/Jupyter)
print("\n=== Evaluation Summary ===")
print(df.to_markdown(index=False, floatfmt=".3f"))

"""
Should look like this:
| env_id       |   win_rate |   loss_rate |   draw_rate |   invalid_rate |   avg_turns |   avg_model_reward |   avg_opponent_reward |
|:-------------|-----------:|------------:|------------:|---------------:|------------:|-------------------:|----------------------:|
| TicTacToe-v0 |      0.500 |       0.375 |       0.125 |          0.000 |       4.125 |              0.125 |                -0.125 |
| Snake-v0     |      0.250 |       0.625 |       0.125 |          0.000 |       3.875 |             -0.458 |                 0.028 |
"""

# Persist to CSV
os.makedirs("eval_results", exist_ok=True)
df.to_csv(f"eval_results/{FILE_NAME}", index=False)
print(f"\nSaved -> eval_results/{FILE_NAME}")
