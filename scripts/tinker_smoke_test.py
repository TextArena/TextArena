#!/usr/bin/env python3
"""Play real games with a model hosted on Tinker, to check what the unit tests' scripted players cannot.

The model plays TicTacToe and Wordle through ``ta.evaluate``, then plays Debate, ScenarioPlanning, GuessWho and
TwentyQuestions while also serving as their jury or game master in place of the OpenRouter judge. Every game is
then replayed from its JSON record, which has to reproduce the game without calling the model again.

The report fails on games that raised and on replays that diverged. It also counts replies without an <action>
tag, which usually means the reply was cut off mid-reasoning, and shows what the jurors answered.

Usage:
    pip install -e . tinker transformers
    TINKER_API_KEY=... python scripts/tinker_smoke_test.py [--model thinkingmachines/Inkling-Small]
"""
import argparse
import collections
import functools
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import textarena as ta
from textarena.utils.jury import JUROR_SYSTEM_PROMPT, OpenRouterJury

EVALUATED = ["TicTacToe-v1", "Wordle-v1"]


class SmokeAgent(ta.agents.TinkerAgent):
    """A TinkerAgent that keeps every reply for the report."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.replies = []
        self.lock = threading.Lock()

    def generate(self, observation: str) -> str:
        reply = super().generate(observation)
        with self.lock:
            self.replies.append(reply)
        return reply


def play(env_id, agent, env_kwargs):
    """Play one game of env_id with agent in every seat; returns (env, error, seconds)."""
    start = time.monotonic()
    env = ta.make(env_id, **env_kwargs)
    try:
        env.reset(seed=0)
        done = False
        while not done:
            _, observation = env.get_observation()
            done = env.step(agent(observation))
        return env, None, time.monotonic() - start
    except Exception as error:
        return env, f"{type(error).__name__}: {error}", time.monotonic() - start


def replays_identically(record, rewards, turns) -> bool:
    replayed = ta.replay(json.loads(json.dumps(record)))
    return replayed.state.done and replayed.state.rewards == rewards and replayed.state.turn == turns


def report(env_id, seats, rewards, turns, invalid, error, replay_ok, seconds=None) -> bool:
    timing = f"{seconds:6.0f}s" if seconds is not None else ""
    if error is not None:
        print(f"  FAIL  {env_id:<20} {seats:<8} {error}")
        return False
    flagged = [pid for pid, value in invalid.items() if value]
    status = "ok  " if replay_ok else "FAIL"
    print(f"  {status}  {env_id:<20} {seats:<8} rewards={rewards} turns={turns} invalid={flagged or '-'} "
          f"replay={'ok' if replay_ok else 'DIVERGED'} {timing}")
    return replay_ok


def untagged(agent) -> str:
    missing = [reply for reply in agent.replies if "<action>" not in reply.lower()]
    summary = f"{len(agent.replies)} replies, {len(missing)} without an <action> tag"
    if missing:
        summary += f"; first one ends with: {missing[0][-200:]!r}"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="thinkingmachines/Inkling-Small", help="Tinker base model (default: %(default)s)")
    parser.add_argument("--max-tokens", type=int, help="reply budget per call (default: TinkerAgent's default)")
    args = parser.parse_args()

    if not os.getenv("TINKER_API_KEY"):
        print("Set TINKER_API_KEY to run the smoke test.")
        return 1
    import tinker

    capabilities = tinker.ServiceClient().get_server_capabilities()
    available = sorted(model.model_name for model in capabilities.supported_models if model.model_name)
    if args.model not in available:
        print(f"{args.model} is not available on Tinker. Available models:\n  " + "\n  ".join(available))
        return 1

    budget = {} if args.max_tokens is None else {"max_tokens": args.max_tokens}
    player = SmokeAgent(model_name=args.model, **budget)
    gamemaster = SmokeAgent(model_name=args.model, **budget)
    juror = SmokeAgent(model_name=args.model, system_prompt=JUROR_SYSTEM_PROMPT, **budget)
    jury_class = functools.partial(OpenRouterJury, model_names=[args.model], agent_factory=lambda **_: juror)
    judged = {
        "Debate-v1": {"jury_class": jury_class},
        "ScenarioPlanning-v1": {"jury_class": jury_class},
        "GuessWho-v1": {"gamemaster": gamemaster},
        "TwentyQuestions-v1": {"gamemaster": gamemaster},
    }
    passed = True

    print(f"Games played through ta.evaluate by {args.model}:")
    start = time.monotonic()
    evaluation = ta.evaluate({"a": player, "b": player}, EVALUATED, episodes=1, workers=4)
    for game in evaluation.games:
        replay_ok = game.error is None and replays_identically(game.record, game.rewards, game.turns)
        passed &= report(game.env_id, ",".join(game.seats), game.rewards, game.turns, game.invalid_moves,
                         game.error, replay_ok)
    print(f"  ({time.monotonic() - start:.0f}s)")

    print(f"\nGames judged or hosted by {args.model}:")
    with ThreadPoolExecutor(max_workers=len(judged)) as pool:
        results = list(pool.map(lambda item: play(item[0], player, item[1]), judged.items()))
    for env_id, (env, error, seconds) in zip(judged, results):
        replay_ok = error is None and replays_identically(env.record(), env.state.rewards, env.state.turn)
        invalid = {pid: info.get("invalid_move") for pid, info in env.state.game_info.items()}
        passed &= report(env_id, "-", env.state.rewards, env.state.turn, invalid, error, replay_ok, seconds)

    print(f"\nPlayer: {untagged(player)}")
    print(f"Game master: {untagged(gamemaster)}")
    votes = collections.Counter(reply.strip() for reply in juror.replies)
    print(f"Jurors: {len(juror.replies)} votes, most common answers: {votes.most_common(5)}")
    print("\nPASSED" if passed else "\nFAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
