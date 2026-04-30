# Avalon Tinker Training & Evaluation Workflow

End-to-end guide for training a custom Avalon LLM agent with `tinker_multiagent.py` and evaluating it with `multi_play.py`.

## Prerequisites

- A Tinker API key (`TINKER_API_KEY`) in `~/TextArena/.env`
- DeepRole binary compiled and `DEEPROLE_*` env vars set
- `tmux` installed on the cluster
- `~/.ssh/config` on your local machine has `ServerAliveInterval 60` for the cluster host (prevents idle SSH disconnects)

Verify before starting:
```bash
cat ~/TextArena/.env                # should contain TINKER_API_KEY=...
which tmux                          # should print a path
tmux ls 2>/dev/null || echo "no tmux sessions yet"
```

## Stage 1 — Training

The training script runs 5-player Avalon self-play with role-aware GRPO. It saves a Tinker sampler checkpoint every `--save-every` steps to `results/tinker_avalon/checkpoints.jsonl`.

### Launch in tmux (survives SSH disconnects)

```bash
tmux new -s train -d "cd ~/TextArena && python textarena/agents/tinker_multiagent.py \
    --base-model Qwen/Qwen3-8B-Base \
    --renderer-name qwen3 \
    --lora-rank 32 \
    --games-per-step 16 \
    --steps 100 \
    --save-every 10 \
    --skip-sft 2>&1 | tee ~/train.log"
```

### Choosing scale

| Goal | `--games-per-step` | `--steps` | Total games | Wall time (~5 min/step) |
|---|---|---|---|---|
| Smoke test (pipeline check) | 2 | 3 | 6 | ~15 min |
| Minimum to maybe see signal | 16 | 100 | 1,600 | ~8 hr |
| Reasonable training run | 32 | 200 | 6,400 | ~16 hr |
| Research-quality | 64 | 500 | 32,000 | ~40+ hr |

### Watching progress

You can attach any time — there's no requirement to wait for a disconnect:

```bash
# Live attach (Ctrl+b then d to detach):
tmux attach -t train

# Or peek at the log without attaching:
tail -f ~/train.log         # follow new output, Ctrl+C to stop
tail -100 ~/train.log       # last 100 lines once

# See if the session is alive:
tmux ls
```

If `tmux ls` doesn't list `train`, the job finished. Read the tail of the log to see if it succeeded or crashed.

### After training completes

View saved checkpoints:
```bash
cat ~/TextArena/results/tinker_avalon/checkpoints.jsonl
```

Each line is one checkpoint with a `sampler_path` like `tinker://UUID:train:0/sampler_weights/step_00100`. Pick the latest (or whichever has the best metrics).

## Stage 2 — Evaluation

`multi_play.py --agent tinker-distil` runs N games using a frozen checkpoint and aggregates win-rate stats. No training, no gradient updates — pure inference.

### Set the checkpoint

Either edit `.env`:
```bash
nano ~/TextArena/.env
# add or replace:
#   TINKER_MODEL=tinker://UUID:train:0/sampler_weights/step_00100
```

Or pass it on the command line (next step). `.env` is more convenient if you'll evaluate the same checkpoint multiple times.

### Run the evaluation

```bash
cd ~/TextArena
python examples/multi_play.py --games 20 --workers 2 --agent tinker-distil 2>&1 | tee ~/eval.log
```

To override `TINKER_MODEL` from the command line:
```bash
python examples/multi_play.py --games 20 --workers 2 --agent tinker-distil \
    --tinker-model tinker://UUID:train:0/sampler_weights/step_00100 2>&1 | tee ~/eval.log
```

For longer evaluations, also use tmux:
```bash
tmux new -s eval -d "cd ~/TextArena && python examples/multi_play.py \
    --games 100 --workers 2 --agent tinker-distil 2>&1 | tee ~/eval.log"
```

### View results

The terminal prints a headline at the end:
```
Headline: agent=tinker-distil  good_wr=65.00%  evil_wr=35.00%
```

Full results live in `results/multi_play_<timestamp>/`:
- `game_logs/game_0000.json` … `game_NNNN.json` — full per-game logs (actions, votes, missions, rewards)
- `summary.json` — aggregated stats: per-seat win rates, per-role breakdown, voting summary, team summary

```bash
ls ~/TextArena/results/multi_play_*/
cat ~/TextArena/results/multi_play_<timestamp>/summary.json | python -m json.tool
```

### Comparing checkpoints

Run `multi_play.py` twice with different `--tinker-model` paths (e.g. `step_00010` vs `step_00100`) and compare the team summaries. If the later checkpoint has a meaningfully higher `good_win_rate` or `evil_win_rate` (depending on which team is being trained more effectively), training is producing real progress.

## Continuous training + evaluation

You can run training and evaluation simultaneously — saved checkpoints are immutable, so evaluating an old one doesn't interfere with ongoing training:

```bash
# Terminal 1 (training):
tmux new -s train -d "cd ~/TextArena && python textarena/agents/tinker_multiagent.py \
    --base-model Qwen/Qwen3-8B-Base --renderer-name qwen3 --lora-rank 32 \
    --games-per-step 16 --steps 200 --save-every 10 --skip-sft 2>&1 | tee ~/train.log"

# Terminal 2 (poll for new checkpoints, eval each):
tmux new -s eval-loop
# Inside:
LAST_STEP=0
while true; do
    if [ -f ~/TextArena/results/tinker_avalon/checkpoints.jsonl ]; then
        LATEST=$(tail -n1 ~/TextArena/results/tinker_avalon/checkpoints.jsonl)
        STEP=$(echo "$LATEST" | python -c "import sys, json; print(json.loads(sys.stdin.read())['step'])")
        PATH_=$(echo "$LATEST" | python -c "import sys, json; print(json.loads(sys.stdin.read())['sampler_path'])")
        if [ "$STEP" -gt "$LAST_STEP" ]; then
            echo "Evaluating step $STEP: $PATH_"
            cd ~/TextArena && python examples/multi_play.py --games 20 --workers 1 \
                --agent tinker-distil --tinker-model "$PATH_" \
                --out-dir "results/eval_step_$STEP" 2>&1 | tee "results/eval_step_$STEP.log"
            LAST_STEP=$STEP
        fi
    fi
    sleep 60
done
```

After it finishes you'll have a folder per checkpoint (`results/eval_step_10/`, `results/eval_step_20/`, …) and can plot win rate over training steps.

**Caveats**:
- Both training and eval consume Tinker API quota. With concurrent rollouts you may hit rate limits — drop `--workers 1` on eval or reduce `--games-per-step` on training.
- A 20-game eval at ~1 min/game is ~20 min wall time (workers=1) or ~10 min (workers=2). Training produces a checkpoint every ~50 min (10 steps × ~5 min). Eval comfortably keeps up.

## Reattach / cleanup cheatsheet

```bash
tmux ls                       # see all sessions
tmux attach -t train          # attach to a session
# (Ctrl+b then d to detach without killing it)

tmux kill-session -t train    # stop a session

# Wipe all results:
rm -rf ~/TextArena/results/*
rm -f ~/train.log ~/eval.log
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `TINKER_API_KEY not set` | `.env` missing or wrong path | `cat ~/TextArena/.env` to verify |
| `ValueError: Environment Avalon-v0 not found in registry` | Importing `textarena` from site-packages instead of repo | Run from `~/TextArena/` and ensure `_REPO_ROOT = parent.parent.parent` in the script |
| `400 — base_model X is not supported` | Tinker doesn't host that model | Use `Qwen/Qwen3-8B-Base` or `meta-llama/Llama-3.2-1B` |
| `403 — You do not have permission to access this model` | `TINKER_MODEL` UUID belongs to someone else's session | Use a path from your own `checkpoints.jsonl` |
| Tmux session shows `[exited]` | Job finished or crashed | `cat ~/train.log` to see why |
| `client_loop: send disconnect: Broken pipe` | SSH timed out | Job still alive in tmux — `ssh ...; tmux attach -t train` |