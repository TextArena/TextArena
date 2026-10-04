<div align="center">

<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/ta_black.svg">
  <img alt="TextArena logo" src="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/ta_white.svg" width="25%" height="25%">
</picture>

108 single-, two-, and multi-player text games for evaluating and training LLM agents.

<h3>

[Games](https://github.com/TextArena/TextArena/blob/main/textarena/envs/README.md) | [Examples](https://github.com/TextArena/TextArena/tree/main/examples) | [Paper](https://arxiv.org/abs/2504.11442) | [Discord](https://discord.gg/dnScm47kNq)

</h3>

[![PyPI version](https://img.shields.io/pypi/v/textarena.svg)](https://pypi.org/project/textarena)
[![PyPI Downloads](https://static.pepy.tech/badge/textarena)](https://pepy.tech/projects/textarena)
[![GitHub Repo stars](https://img.shields.io/github/stars/TextArena/TextArena)](https://github.com/TextArena/TextArena/stargazers)
[![Discord](https://img.shields.io/discord/1257951838322561075?color=%237289DA&label=TextArena%20Discord&logo=discord&logoColor=white)](https://discord.gg/dnScm47kNq)
[![arXiv](https://img.shields.io/badge/arXiv-2504.11442-b31b1b.svg)](https://arxiv.org/abs/2504.11442)

</div>

TextArena puts board and card games, puzzles, negotiation, social deduction, and other multi-agent tasks behind
one Gym-style interface. Every game enforces its own rules, shows each player only what they may see, and returns
rewards, so models can be evaluated against each other or trained through self-play. A seed replays a game
exactly, and observations can be translated into 192 languages. Upgrading from 0.x? See the
[changelog](https://github.com/TextArena/TextArena/blob/main/CHANGELOG.md) for what changed in 1.0 and how to migrate.

## Installation

```bash
pip install "textarena[agents]"
```

TextArena needs Python 3.10 or newer. The games themselves have no dependencies, so `pip install textarena` installs
nothing else; the extras add the optional parts: `agents` (model agents, via `openai`), `render` (the terminal
renderer, via `rich`), `translations` (the `textarena-locales` catalogs), and `all`.

## Quick start

Two models play TicTacToe through [OpenRouter](https://openrouter.ai) (set `OPENROUTER_API_KEY` first):

```python
import textarena as ta

agents = {
    0: ta.agents.OpenRouterAgent(model_name="openai/gpt-5-mini"),
    1: ta.agents.OpenRouterAgent(model_name="qwen/qwen3.8-27b"),
}

env = ta.make("TicTacToe-v1")
env.reset(num_players=len(agents), seed=42)

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done = env.step(action)

rewards, game_info = env.close()
```

`get_observation()` returns the player who acts next and the text they see, `step()` returns whether the game is
over, and `close()` returns each player's reward and game info. An agent is any callable that turns an observation string into an action string. TextArena ships
`OpenAIAgent` for any OpenAI-compatible API (OpenAI, a vLLM or other local server via `base_url`), its OpenRouter
preset `OpenRouterAgent`, `TinkerAgent` for models trained with Tinker, and `HumanAgent` for playing in the terminal
(try `python demo.py`).

## Actions

Games take bare actions such as `4`, `roll`, or `e2e4`. Models are asked to reason freely and put their move inside
`<action>...</action>` tags; the built-in agents pass only the tag contents to `env.step`, and
`ta.extract_action(response)` does the same for your own agents. An invalid action is never applied: the player is
told why and can try again once, and a second invalid action in a row ends their game (or their turn, depending on
the game).

## Observations

Every configuration is registered twice:

| ID | Each observation contains | Use it when |
| --- | --- | --- |
| `TicTacToe-v1` | only the messages since the player's last turn | the agent keeps the conversation history itself |
| `TicTacToe-v1-mdp` | everything needed to act: the prompt, the game's messages, and the latest board | each step should stand on its own, as in RL training |

## Games

There are 30 single-player, 52 two-player, and 26 multi-player games. The [catalog](https://github.com/TextArena/TextArena/blob/main/textarena/envs/README.md)
lists them all, and each game's README covers its rules, actions, rewards, registered configurations, and
parameters. Settings that are not registered are a keyword away: `ta.make("Chess-v1", max_turns=250)`.

Rewards use one scale per kind of game: `+1` win, `-1` loss and `0` draw in competitive games; a score from `0` to
`1` in single-player games; and each player's own score from `0` to `1` in cooperative and mixed-motive games such
as Hanabi and PublicGoodsGame.

Environment ids end in a version: when a game's rules change, the version goes up and the old id is retired, so
scores reported for one version are only comparable with scores for the same version. All ids are currently `-v1`.

## Replaying games

Every game can be rebuilt from its seed and actions. `env.record()` returns a JSON-serializable record of the game
(its parameters, player count, seed, actions, and the answers of any LLM judge), and `ta.replay(record)` rebuilds it,
optionally stopping after a given number of actions:

```python
record = env.record()
replayed = ta.replay(record, steps=10)  # the game after its first ten actions
```

## Evaluating models

`ta.evaluate` plays agents against each other and summarizes the results. Every agent plays every seat equally often
on the same seeds, so first-mover advantage and lucky deals cancel out, and games run in parallel threads:

```python
evaluation = ta.evaluate(
    {"gpt": ta.agents.OpenRouterAgent("openai/gpt-5-mini"), "qwen": ta.agents.OpenRouterAgent("qwen/qwen3.8-27b")},
    ["TicTacToe-v1", "Chess-v1", "Wordle-v1"],
    episodes=20,
    workers=8,
)
evaluation.summary()  # per agent and game: games, mean reward, win rate, invalid-move rate, mean turns, errors
```

Each game in `evaluation.games` keeps its seed, seating, rewards, and `record`, so any game can be replayed, and
`evaluation.to_rows()` gives one row per seat for analysis with pandas. A game that fails, for example because a
model is unreachable, is recorded with its error instead of stopping the evaluation.

## Training

[`examples/tinker`](https://github.com/TextArena/TextArena/tree/main/examples/tinker) is a compact self-play RL loop on Tinker. Projects built on TextArena include:

- [SPIRAL](https://arxiv.org/pdf/2506.24119): reinforcement learning through self-play on zero-sum games improves
  reasoning.
- [UnstableBaselines](https://github.com/LeonGuertler/UnstableBaselines): a lightweight asynchronous online RL
  library for TextArena games.
- [MindGames](https://www.mindgamesarena.com/): a NeurIPS 2025 competition on games that require theory of mind,
  with released [trajectories](https://huggingface.co/datasets/mindgameschallenge/MGC2025) and
  [findings](https://arxiv.org/pdf/2605.29512).

## Watching and recording games

`ta.wrappers.SimpleRenderWrapper(env)` draws the board and the conversation in the terminal. With
`record_dir="frames", record_only=True` it saves every frame as a fixed-size SVG instead, which is how the GIFs
below were made.

## Multilingual games

Games are written in English. `TranslationWrapper` translates each player's observations into that player's
language, even when players in the same match use different languages. The translations ship separately
(`pip install "textarena[translations]"`):

```python
env = ta.make("TicTacToe-v1")
env = ta.wrappers.TranslationWrapper(env, lang={0: "en", 1: "de"})
```

Actions always stay in English, since that is what the games parse. Translations are keyed by the exact English
line, so a line whose English wording changes falls back to English instead of showing an outdated translation.
`python scripts/locales.py coverage --lang de` reports how much of each game is translated.

<div align="center">

<img src="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/othello.gif" alt="Multilingual Othello in TextArena" width="48%">
<img src="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/connectfour.gif" alt="Multilingual Connect Four in TextArena" width="48%">
<img src="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/simpletak.gif" alt="Multilingual SimpleTak in TextArena" width="48%">
<img src="https://raw.githubusercontent.com/TextArena/TextArena/main/docs/nim.gif" alt="Multilingual Nim in TextArena" width="48%">

</div>

Of the 192 languages, 8 are reviewed by native speakers, 42 high- and mid-resource languages are translated and
automatically verified, and 142 low-resource languages are machine-translated and machine-verified.
`TranslationWrapper` emits a `UserWarning` when you select one of the low-resource languages.

<details>
<summary><b>How the low-resource translations were made and verified</b></summary>

The 142 low-resource localizations are produced with **NLLB-200** and checked for meaning fidelity by two
independent model families, **Llama-3.1-405B** and **Qwen2.5-72B**. Strings both judges accept are kept;
disagreements are settled by an additional Llama-3.1-405B judgment. Confirmed errors are repaired under structural
checks that preserve placeholders, command tokens, and template slots.

Languages fall into two confidence tiers:

* **Certified-flagged:** meaning fidelity of at least 85% before repair.
* **Experimental:** meaning fidelity below 85% before repair; structurally valid and repaired, but with
  substantially more machine correction.

All shipped low-resource localizations reach at least 94% measured fidelity after repair. Per-language scores are
in [`locales/textarena_locales/confidence.json`](https://github.com/TextArena/TextArena/blob/main/locales/textarena_locales/confidence.json), and the pipeline that
translated, verified, and repaired them is on the
[`multilingual`](https://github.com/TextArena/TextArena/tree/multilingual) branch. Research using these
localizations should report each language's confidence tier and distinguish machine-verified from native-reviewed
translations.

</details>

## Contributing

Contributions of all kinds are welcome: new games, fixes, documentation, and translations. To work on TextArena:

```bash
pip install -e ./locales -e ".[test]"
pytest
```

[Adding a game](https://github.com/TextArena/TextArena/blob/main/textarena/envs/README.md#adding-a-game) describes the folder layout and the engine hooks. After
changing a game, `python scripts/generate_env_docs.py` updates the generated parts of the docs and
`python scripts/locales.py extract` updates the translation catalogs in [`locales/`](https://github.com/TextArena/TextArena/tree/main/locales), the source of the
`textarena-locales` package. Questions and ideas are welcome on [Discord](https://discord.gg/dnScm47kNq).

## Citation

```bibtex
@misc{guertler2025textarena,
    title={TextArena},
    author={Leon Guertler and Bobby Cheng and Simon Yu and Bo Liu and Leshem Choshen and Cheston Tan},
    year={2025},
    eprint={2504.11442},
    archivePrefix={arXiv},
    primaryClass={cs.CL},
    url={https://arxiv.org/abs/2504.11442},
}
```
