<div align="center">
<picture>
  <source media="(prefers-color-scheme: light)" srcset="/docs/ta_black.svg">
  <img alt="TextArena logo" src="/docs/ta_white.svg" width="25%" height="25%">
</picture>
  
A suite of 100+ {single,two,multi}-Player texted based games for benchmarking and training of LLMs.

<h3>

[Play](https://textarena.ai) | [Leaderboard](https://textarena.ai/leaderboard) | [Games](https://github.com/LeonGuertler/TextArena/blob/main/textarena/envs/README.md) | [Examples](https://github.com/LeonGuertler/TextArena/tree/main/examples)

</h3>

[![GitHub Repo stars](https://img.shields.io/github/stars/LeonGuertler/TextArena)](https://github.com/LeonGuertler/TextArena/stargazers)
[![PyPI Downloads](https://static.pepy.tech/badge/textarena)](https://pepy.tech/projects/textarena)
[![Discord](https://img.shields.io/discord/1257951838322561075?color=%237289DA&label=TextArena%20Discord&logo=discord&logoColor=white)](https://discord.gg/KPacHzK23e)
[![PyPI version](https://img.shields.io/pypi/v/textarena.svg)](https://pypi.org/project/textarena)

</div>

## Updates
* **31/07/2025** We added **SettlersOfCatan** to TextArena!
* **14/07/2025** Announcing **MindGames** a NeurIPS2025 competition for training LLMs on various TextArena games that require theory of mind.
* **01/07/2025** Release of v0.6.9 with **100** games and simplified states, new observation wrappers for training and default wrappers for environments. 
* **01/07/2025** Release of __SPIRAL: Self-Play on Zero-Sum Games Incentivizes Reasoning via Multi-Agent Multi-Turn Reinforcement Learning__ introducing RL via self-play on TextArena games as a potential new training paradigm.
* **22/06/2025** Release of [UnstableBaselines](https://github.com/LeonGuertler/UnstableBaselines) a light weight async online RL library for training LLMs on TextArena games. 
* **16/04/2025** Release of the TextArena paper 
* **14/02/2025** Release of the new, stable version for both pip and the website
* **31/01/2025** Initial demo release highlighted by Andrej Karpathy (crashing all our servers)


## Introduction
**TextArena** is a flexible and extensible framework for training, evaluating, and benchmarking models in text-based games. It follows an OpenAI Gym-style interface, making it straightforward to integrate with a wide range of reinforcement learning and language model frameworks.


## Getting Started

### Installation
Install TextArena directly from PyPI:
```bash
pip install textarena
```

### Offline Play
The only requirement __Agents__ need to fulfill is having a __call__ function that accepts string observations and returns string action. We have implemented a number of basic agents that you can find [here](https://github.com/LeonGuertler/TextArena/blob/main/textarena/agents/basic_agents.py). In this example, we show how you can let **GPT-4o-mini** play against **anthropic/claude-3.5-haiku** in a game of __TicTacToe__.


We will be using the OpenRouterAgent, so first you need to set you OpenRouter API key:
```bash
export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
```

Now we can build the models and let them play:

```python
import textarena as ta

# Initialize agents
agents = {
    0: ta.agents.OpenRouterAgent(model_name="GPT-4o-mini"),
    1: ta.agents.OpenRouterAgent(model_name="anthropic/claude-3.5-haiku"),
}

# Initialize the environment
env = ta.make(env_id="TicTacToe-v0")

# wrap it for additional visualizations
env = ta.wrappers.SimpleRenderWrapper(env=env) 

env.reset(num_players=len(agents))

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action=action)

rewards, game_info = env.close()
```



## Citation [![arXiv](https://img.shields.io/badge/arXiv-2504.11442-b31b1b.svg)](https://arxiv.org/abs/2504.11442)

If you use **TextArena** in your research, please cite:

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



## How to Contribute:
If you have any questions at all, feel free to reach out on discord. The below issues are great starting points if you want to contribute:
- Transfer the 'How to Contribute' from here to individual issues
- Make RushHour board generation algorithmic
- extend Fifteenpuzzel to arbitrary sizes
- Add a nice end-of-game screen to the SimpleRenderWrapper visualizations

<!-- BEGIN trackb-low-resource -->

### Low-resource community localizations

Beyond the human-reviewed languages, TextArena includes **30 additional low-resource UI localizations** produced with open machine-translation models and checked by an automatic, *reader-free* verifier: each string is translated, independently back-translated by two other models, and an LLM judges faithfulness against the English source. **No claim is made of native-review quality.** Every back-translation-confirmed divergence is **reverted to English**, so no *known*-wrong string ships; the counts below are how many leaves were reverted (a proxy for residual risk). Each language carries an explicit **confidence tier**. At runtime, `textarena.utils.locales.language_confidence.warn_if_flagged(lang)` emits a `UserWarning` for any non-certified locale; the machine-readable source is [`_trackb_confidence.json`](textarena/utils/locales/_trackb_confidence.json).

**Certified-flagged** (4) — verified; a few games flagged:

| Language | Tier | Confirmed (reverted) | Flagged games |
|---|---|---|---|
| Kannada (`kn`) | CERTIFIED_FLAGGED | 12 | Breakthrough, Briscola, ColonelBlotto, ConnectFour +6 more |
| Punjabi (`pa`) | CERTIFIED_FLAGGED | 19 | Alquerque, Breakthrough, Briscola, Checkers +11 more |
| Gujarati (`gu`) | CERTIFIED_FLAGGED | 22 | Alquerque, Breakthrough, Briscola, Crusade +14 more |
| Belarusian (`be`) | CERTIFIED_FLAGGED | 26 | Battleship, Breakthrough, Briscola, Chopsticks +16 more |

> ⚠️ **Experimental** (26) — structurally valid and playable, but the prose is **not certified** and likely contains further errors the verifier missed. Use for coverage/research, not as a reference translation:

| Language | Tier | Confirmed (reverted) | Flagged games |
|---|---|---|---|
| Marathi (`mr`) | EXPERIMENTAL | 31 | Checkers, ColonelBlotto, Cryptarithm, FifteenPuzzle +19 more |
| Pashto (`ps`) | EXPERIMENTAL | 36 | Breakthrough, Checkers, Chopsticks, ColonelBlotto +21 more |
| Telugu (`te`) | EXPERIMENTAL | 38 | Blackjack, Breakthrough, Briscola, Checkers +24 more |
| Sindhi (`sd`) | EXPERIMENTAL | 42 | Alquerque, Blackjack, Breakthrough, Briscola +24 more |
| Nepali (`ne`) | EXPERIMENTAL | 43 | Alquerque, Bandit, Checkers, ColonelBlotto +22 more |
| Lao (`lo`) | EXPERIMENTAL | 44 | Breakthrough, Chess, Cryptarithm, FrozenLake +25 more |
| Uzbek (`uz`) | EXPERIMENTAL | 45 | Alquerque, Breakthrough, Briscola, Chopsticks +26 more |
| Malayalam (`ml`) | EXPERIMENTAL | 48 | Alquerque, Battleship, Breakthrough, Briscola +22 more |
| Zulu (`zu`) | EXPERIMENTAL | 49 | Battleship, Breakthrough, Briscola, Checkers +27 more |
| Assamese (`as`) | EXPERIMENTAL | 53 | Alquerque, Bandit, Breakthrough, Briscola +22 more |
| Khmer (`km`) | EXPERIMENTAL | 54 | Alquerque, Bandit, Battleship, Breakthrough +29 more |
| Armenian (`hy`) | EXPERIMENTAL | 55 | Alquerque, Bandit, Blackjack, Breakthrough +35 more |
| Welsh (`cy`) | EXPERIMENTAL | 58 | Alquerque, Battleship, Blackjack, Checkers +31 more |
| Sinhala (`si`) | EXPERIMENTAL | 64 | Alquerque, Bandit, Blackjack, Briscola +36 more |
| Kazakh (`kk`) | EXPERIMENTAL | 66 | Alquerque, Bandit, Battleship, Breakthrough +33 more |
| Odia (`or`) | EXPERIMENTAL | 70 | Alquerque, Briscola, Checkers, Chess +36 more |
| Burmese (`my`) | EXPERIMENTAL | 70 | Alquerque, Briscola, ColonelBlotto, Countdown +30 more |
| Somali (`so`) | EXPERIMENTAL | 71 | Alquerque, Bandit, Battleship, Breakthrough +37 more |
| Malagasy (`mg`) | EXPERIMENTAL | 80 | Bandit, Blackjack, Breakthrough, Briscola +42 more |
| Kyrgyz (`ky`) | EXPERIMENTAL | 82 | Alquerque, Battleship, Blackjack, Breakthrough +44 more |
| Georgian (`ka`) | EXPERIMENTAL | 101 | Alquerque, Bandit, Battleship, Breakthrough +41 more |
| Hausa (`ha`) | EXPERIMENTAL | 108 | Alquerque, Bandit, Battleship, Blackjack +46 more |
| Igbo (`ig`) | EXPERIMENTAL | 118 | Alquerque, Bandit, Breakthrough, Briscola +47 more |
| Mongolian (`mn`) | EXPERIMENTAL | 134 | Alquerque, Battleship, Blackjack, Breakthrough +49 more |
| Basque (`eu`) | EXPERIMENTAL | 137 | Battleship, Blackjack, Breakthrough, Briscola +47 more |
| Yoruba (`yo`) | EXPERIMENTAL | 162 | Alquerque, Battleship, Blackjack, Briscola +46 more |

Languages move from experimental to certified as verification improves; the list grows over time.

<!-- END trackb-low-resource -->
