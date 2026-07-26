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

Beyond the human-reviewed languages, TextArena includes **143 additional low-resource UI localizations** produced with open machine-translation models and checked by an automatic, *reader-free* verifier: each string is translated, independently back-translated by two other models, and an LLM judges faithfulness against the English source. **No claim is made of native-review quality.** Every back-translation-confirmed divergence is **reverted to English**, so no *known*-wrong string ships; the counts below are how many leaves were reverted (a proxy for residual risk). Each language carries an explicit **confidence tier**. At runtime, `textarena.utils.locales.language_confidence.warn_if_flagged(lang)` emits a `UserWarning` for any non-certified locale; the machine-readable source is [`_trackb_confidence.json`](textarena/utils/locales/_trackb_confidence.json).

**Certified-flagged** (4) — verified; a few games flagged:

| Language | Tier | Translated coverage | Confirmed (reverted) | Flagged games |
|---|---|---|---|---|
| Kannada (`kn`) | CERTIFIED_FLAGGED | ~97% | 12 | Breakthrough, Briscola, ColonelBlotto, ConnectFour +6 more |
| Punjabi (`pa`) | CERTIFIED_FLAGGED | ~95% | 19 | Alquerque, Breakthrough, Briscola, Checkers +11 more |
| Gujarati (`gu`) | CERTIFIED_FLAGGED | ~97% | 22 | Alquerque, Breakthrough, Briscola, Crusade +14 more |
| Belarusian (`be`) | CERTIFIED_FLAGGED | ~97% | 26 | Battleship, Breakthrough, Briscola, Chopsticks +16 more |

> ⚠️ **Experimental** (139) — structurally valid and playable, but the prose is **not certified** and likely contains further errors the verifier missed. Use for coverage/research, not as a reference translation:

| Language | Tier | Translated coverage | Confirmed (reverted) | Flagged games |
|---|---|---|---|---|
| Marathi (`mr`) | EXPERIMENTAL | ~94% | 31 | Checkers, ColonelBlotto, Cryptarithm, FifteenPuzzle +19 more |
| Esperanto (`epo`) | EXPERIMENTAL | ~92% | 33 | Blackjack, Checkers, Chopsticks, ColonelBlotto +19 more |
| Pashto (`ps`) | EXPERIMENTAL | ~92% | 36 | Breakthrough, Checkers, Chopsticks, ColonelBlotto +21 more |
| Javanese (`jav`) | EXPERIMENTAL | ~91% | 36 | Battleship, Blackjack, Briscola, Chopsticks +20 more |
| Sundanese (`sun`) | EXPERIMENTAL | ~92% | 36 | Battleship, Blackjack, Briscola, Checkers +23 more |
| Telugu (`te`) | EXPERIMENTAL | ~92% | 38 | Blackjack, Breakthrough, Briscola, Checkers +24 more |
| ceb (`ceb`) | EXPERIMENTAL | ~88% | 38 | Bandit, Battleship, Blackjack, Briscola +25 more |
| Sindhi (`sd`) | EXPERIMENTAL | ~92% | 42 | Alquerque, Blackjack, Breakthrough, Briscola +24 more |
| Nepali (`ne`) | EXPERIMENTAL | ~91% | 43 | Alquerque, Bandit, Checkers, ColonelBlotto +22 more |
| Lao (`lo`) | EXPERIMENTAL | ~91% | 44 | Breakthrough, Chess, Cryptarithm, FrozenLake +25 more |
| Sicilian (`scn`) | EXPERIMENTAL | ~90% | 44 | Blackjack, Chopsticks, ColonelBlotto, FrozenLake +24 more |
| Uzbek (`uz`) | EXPERIMENTAL | ~92% | 45 | Alquerque, Breakthrough, Briscola, Chopsticks +26 more |
| Malayalam (`ml`) | EXPERIMENTAL | ~91% | 48 | Alquerque, Battleship, Breakthrough, Briscola +22 more |
| Zulu (`zu`) | EXPERIMENTAL | ~91% | 49 | Battleship, Breakthrough, Briscola, Checkers +27 more |
| Venetian (`vec`) | EXPERIMENTAL | ~90% | 51 | Alquerque, Blackjack, Breakthrough, Briscola +31 more |
| Haitian Creole (`hat`) | EXPERIMENTAL | ~89% | 52 | Alquerque, Chess, Chopsticks, ColonelBlotto +25 more |
| Assamese (`as`) | EXPERIMENTAL | ~90% | 53 | Alquerque, Bandit, Breakthrough, Briscola +22 more |
| Khmer (`km`) | EXPERIMENTAL | ~89% | 54 | Alquerque, Bandit, Battleship, Breakthrough +29 more |
| Armenian (`hy`) | EXPERIMENTAL | ~90% | 55 | Alquerque, Bandit, Blackjack, Breakthrough +35 more |
| Lombard (`lmo`) | EXPERIMENTAL | ~84% | 56 | Alquerque, Bandit, Battleship, Briscola +32 more |
| Papiamento (`pap`) | EXPERIMENTAL | ~88% | 57 | Bandit, Blackjack, Checkers, Chopsticks +26 more |
| Eastern Yiddish (`ydd`) | EXPERIMENTAL | ~86% | 57 | Alquerque, Breakthrough, Checkers, Chess +34 more |
| Welsh (`cy`) | EXPERIMENTAL | ~89% | 58 | Alquerque, Battleship, Blackjack, Checkers +31 more |
| Banjar (`bjn`) | EXPERIMENTAL | ~88% | 62 | Blackjack, Breakthrough, Briscola, Chopsticks +32 more |
| Sinhala (`si`) | EXPERIMENTAL | ~88% | 64 | Alquerque, Bandit, Blackjack, Briscola +36 more |
| Najdi Arabic (`ars`) | EXPERIMENTAL | ~89% | 64 | Alquerque, Blackjack, Breakthrough, Briscola +29 more |
| Egyptian Arabic (`arz`) | EXPERIMENTAL | ~88% | 64 | Alquerque, Blackjack, Breakthrough, Chess +34 more |
| Limburgish (`lim`) | EXPERIMENTAL | ~88% | 64 | Battleship, Blackjack, Breakthrough, Checkers +32 more |
| Occitan (`oci`) | EXPERIMENTAL | ~88% | 64 | Blackjack, Briscola, Checkers, Chopsticks +27 more |
| Tajik (`tgk`) | EXPERIMENTAL | ~87% | 64 | Blackjack, Breakthrough, Briscola, Checkers +29 more |
| Taizzi-Adeni Arabic (`acq`) | EXPERIMENTAL | ~88% | 65 | Blackjack, Breakthrough, Briscola, Checkers +32 more |
| Kazakh (`kk`) | EXPERIMENTAL | ~88% | 66 | Alquerque, Bandit, Battleship, Breakthrough +33 more |
| Odia (`or`) | EXPERIMENTAL | ~88% | 70 | Alquerque, Briscola, Checkers, Chess +36 more |
| Burmese (`my`) | EXPERIMENTAL | ~88% | 70 | Alquerque, Briscola, ColonelBlotto, Countdown +30 more |
| Scottish Gaelic (`gla`) | EXPERIMENTAL | ~84% | 70 | Alquerque, Battleship, Breakthrough, Briscola +36 more |
| Southern Sotho (`sot`) | EXPERIMENTAL | ~85% | 70 | Alquerque, Battleship, Blackjack, Breakthrough +37 more |
| Somali (`so`) | EXPERIMENTAL | ~88% | 71 | Alquerque, Bandit, Battleship, Breakthrough +37 more |
| Amharic (`am`) | EXPERIMENTAL | ~83% | 71 | Alquerque, Blackjack, Breakthrough, Briscola +32 more |
| Crimean Tatar (`crh`) | EXPERIMENTAL | ~86% | 71 | Blackjack, Breakthrough, Briscola, Checkers +38 more |
| North Levantine Arabic (`apc`) | EXPERIMENTAL | ~88% | 71 | Alquerque, Battleship, Blackjack, Breakthrough +39 more |
| Luxembourgish (`ltz`) | EXPERIMENTAL | ~86% | 71 | Bandit, Blackjack, Breakthrough, Briscola +37 more |
| Chhattisgarhi (`hne`) | EXPERIMENTAL | ~87% | 71 | Alquerque, Bandit, Battleship, Blackjack +42 more |
| Friulian (`fur`) | EXPERIMENTAL | ~86% | 74 | Alquerque, Battleship, Blackjack, Breakthrough +39 more |
| Maithili (`mai`) | EXPERIMENTAL | ~87% | 74 | Alquerque, Battleship, Blackjack, Breakthrough +38 more |
| South Levantine Arabic (`ajp`) | EXPERIMENTAL | ~88% | 75 | Alquerque, Blackjack, Breakthrough, Briscola +40 more |
| Irish (`gle`) | EXPERIMENTAL | ~87% | 75 | Battleship, Blackjack, Breakthrough, Briscola +36 more |
| Minangkabau (`min`) | EXPERIMENTAL | ~86% | 77 | Battleship, Blackjack, Breakthrough, Briscola +42 more |
| Bhojpuri (`bho`) | EXPERIMENTAL | ~86% | 78 | Alquerque, Bandit, Battleship, Blackjack +43 more |
| Xhosa (`xho`) | EXPERIMENTAL | ~82% | 78 | Alquerque, Battleship, Breakthrough, Briscola +35 more |
| Balinese (`ban`) | EXPERIMENTAL | ~87% | 79 | Alquerque, Bandit, Battleship, Blackjack +41 more |
| Malagasy (`mg`) | EXPERIMENTAL | ~87% | 80 | Bandit, Blackjack, Breakthrough, Briscola +42 more |
| Kyrgyz (`ky`) | EXPERIMENTAL | ~87% | 82 | Alquerque, Battleship, Blackjack, Breakthrough +44 more |
| Acehnese (`ace`) | EXPERIMENTAL | ~86% | 83 | Alquerque, Bandit, Battleship, Blackjack +41 more |
| Faroese (`fao`) | EXPERIMENTAL | ~85% | 85 | Bandit, Breakthrough, Briscola, Checkers +33 more |
| Magahi (`mag`) | EXPERIMENTAL | ~85% | 86 | Alquerque, Battleship, Blackjack, Breakthrough +41 more |
| Nyanja (`nya`) | EXPERIMENTAL | ~85% | 86 | Alquerque, Blackjack, Briscola, Checkers +41 more |
| Shona (`sna`) | EXPERIMENTAL | ~83% | 87 | Alquerque, Bandit, Battleship, Blackjack +45 more |
| Sardinian (`srd`) | EXPERIMENTAL | ~84% | 89 | Alquerque, Battleship, Blackjack, Breakthrough +39 more |
| Samoan (`smo`) | EXPERIMENTAL | ~85% | 89 | Alquerque, Blackjack, Breakthrough, Briscola +41 more |
| Mesopotamian Arabic (`acm`) | EXPERIMENTAL | ~86% | 90 | Alquerque, Bandit, Blackjack, Breakthrough +39 more |
| Northern Kurdish (`kmr`) | EXPERIMENTAL | ~82% | 90 | Alquerque, Bandit, Battleship, Breakthrough +43 more |
| Silesian (`szl`) | EXPERIMENTAL | ~85% | 91 | Alquerque, Bandit, Breakthrough, Briscola +39 more |
| Moroccan Arabic (`ary`) | EXPERIMENTAL | ~85% | 95 | Alquerque, Bandit, Battleship, Blackjack +40 more |
| Maori (`mri`) | EXPERIMENTAL | ~84% | 95 | Alquerque, Breakthrough, Briscola, Checkers +44 more |
| Waray (`war`) | EXPERIMENTAL | ~82% | 97 | Blackjack, Breakthrough, Briscola, Chopsticks +39 more |
| Awadhi (`awa`) | EXPERIMENTAL | ~84% | 98 | Alquerque, Battleship, Breakthrough, Briscola +47 more |
| Maltese (`mlt`) | EXPERIMENTAL | ~83% | 99 | Battleship, Blackjack, Breakthrough, Briscola +39 more |
| Norwegian Nynorsk (`nno`) | EXPERIMENTAL | ~84% | 99 | Alquerque, Battleship, Breakthrough, Briscola +37 more |
| Ilocano (`ilo`) | EXPERIMENTAL | ~81% | 100 | Alquerque, Battleship, Blackjack, Breakthrough +46 more |
| Georgian (`ka`) | EXPERIMENTAL | ~84% | 101 | Alquerque, Bandit, Battleship, Breakthrough +41 more |
| Ligurian (`lij`) | EXPERIMENTAL | ~83% | 101 | Battleship, Breakthrough, Briscola, Checkers +41 more |
| Pangasinan (`pag`) | EXPERIMENTAL | ~80% | 102 | Bandit, Battleship, Blackjack, Breakthrough +48 more |
| Central Kurdish (`ckb`) | EXPERIMENTAL | ~81% | 105 | Bandit, Blackjack, Briscola, Chess +43 more |
| Hausa (`ha`) | EXPERIMENTAL | ~83% | 108 | Alquerque, Bandit, Battleship, Blackjack +46 more |
| Tunisian Arabic (`aeb`) | EXPERIMENTAL | ~83% | 109 | Alquerque, Bandit, Battleship, Blackjack +50 more |
| Kashmiri (`kas`) | EXPERIMENTAL | ~77% | 114 | Alquerque, Bandit, Battleship, Breakthrough +46 more |
| Meitei (`mni`) | EXPERIMENTAL | ~64% | 117 | Alquerque, Bandit, Battleship, Blackjack +51 more |
| Igbo (`ig`) | EXPERIMENTAL | ~82% | 118 | Alquerque, Bandit, Breakthrough, Briscola +47 more |
| Tatar (`tat`) | EXPERIMENTAL | ~79% | 120 | Alquerque, Bandit, Battleship, Briscola +41 more |
| Uyghur (`uig`) | EXPERIMENTAL | ~78% | 121 | Alquerque, Battleship, Blackjack, Breakthrough +48 more |
| Asturian (`ast`) | EXPERIMENTAL | ~82% | 122 | Bandit, Battleship, Blackjack, Breakthrough +48 more |
| Tigrinya (`tir`) | EXPERIMENTAL | ~73% | 126 | Alquerque, Bandit, Battleship, Blackjack +48 more |
| Tsonga (`tso`) | EXPERIMENTAL | ~80% | 127 | Alquerque, Battleship, Blackjack, Breakthrough +45 more |
| Turkmen (`tuk`) | EXPERIMENTAL | ~79% | 129 | Alquerque, Bandit, Battleship, Blackjack +53 more |
| Mizo (`lus`) | EXPERIMENTAL | ~71% | 131 | Bandit, Battleship, Blackjack, Breakthrough +53 more |
| Mongolian (`mn`) | EXPERIMENTAL | ~81% | 134 | Alquerque, Battleship, Blackjack, Breakthrough +49 more |
| Kinyarwanda (`kin`) | EXPERIMENTAL | ~78% | 135 | Alquerque, Bandit, Battleship, Blackjack +46 more |
| Basque (`eu`) | EXPERIMENTAL | ~80% | 137 | Battleship, Blackjack, Breakthrough, Briscola +47 more |
| Northern Sotho (`nso`) | EXPERIMENTAL | ~78% | 138 | Alquerque, Blackjack, Breakthrough, Briscola +46 more |
| Swati (`ssw`) | EXPERIMENTAL | ~77% | 138 | Alquerque, Battleship, Blackjack, Breakthrough +54 more |
| Bashkir (`bak`) | EXPERIMENTAL | ~75% | 141 | Alquerque, Bandit, Battleship, Blackjack +48 more |
| Latgalian (`ltg`) | EXPERIMENTAL | ~79% | 141 | Alquerque, Battleship, Blackjack, Breakthrough +49 more |
| Kabuverdianu (`kea`) | EXPERIMENTAL | ~78% | 146 | Bandit, Battleship, Blackjack, Breakthrough +43 more |
| Tswana (`tsn`) | EXPERIMENTAL | ~77% | 146 | Alquerque, Battleship, Blackjack, Briscola +53 more |
| Sanskrit (`san`) | EXPERIMENTAL | ~78% | 148 | Alquerque, Bandit, Battleship, Breakthrough +50 more |
| Fijian (`fij`) | EXPERIMENTAL | ~74% | 154 | Alquerque, Bandit, Battleship, Blackjack +49 more |
| Buginese (`bug`) | EXPERIMENTAL | ~78% | 155 | Alquerque, Bandit, Battleship, Blackjack +48 more |
| Rundi (`run`) | EXPERIMENTAL | ~76% | 155 | Alquerque, Bandit, Battleship, Blackjack +54 more |
| Yoruba (`yo`) | EXPERIMENTAL | ~78% | 162 | Alquerque, Battleship, Blackjack, Briscola +46 more |
| Guarani (`grn`) | EXPERIMENTAL | ~75% | 168 | Alquerque, Bandit, Battleship, Blackjack +56 more |
| West Central Oromo (`gaz`) | EXPERIMENTAL | ~69% | 179 | Alquerque, Bandit, Battleship, Blackjack +55 more |
| South Azerbaijani (`azb`) | EXPERIMENTAL | ~73% | 182 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Lingala (`lin`) | EXPERIMENTAL | ~74% | 184 | Alquerque, Battleship, Blackjack, Breakthrough +56 more |
| Ganda (`lug`) | EXPERIMENTAL | ~72% | 193 | Alquerque, Bandit, Battleship, Blackjack +54 more |
| Tok Pisin (`tpi`) | EXPERIMENTAL | ~71% | 195 | Alquerque, Bandit, Battleship, Blackjack +55 more |
| Luo (`luo`) | EXPERIMENTAL | ~71% | 206 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Shan (`shn`) | EXPERIMENTAL | ~65% | 209 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Santali (`sat`) | EXPERIMENTAL | ~64% | 215 | Alquerque, Battleship, Blackjack, Breakthrough +58 more |
| Tumbuka (`tum`) | EXPERIMENTAL | ~70% | 219 | Alquerque, Bandit, Battleship, Blackjack +54 more |
| Standard Tibetan (`bod`) | EXPERIMENTAL | ~65% | 223 | Alquerque, Bandit, Battleship, Blackjack +54 more |
| Luba-Kasai (`lua`) | EXPERIMENTAL | ~69% | 232 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Ayacucho Quechua (`quy`) | EXPERIMENTAL | ~67% | 233 | Alquerque, Bandit, Blackjack, Breakthrough +57 more |
| Jingpho (`kac`) | EXPERIMENTAL | ~56% | 237 | Alquerque, Bandit, Battleship, Blackjack +56 more |
| Ewe (`ewe`) | EXPERIMENTAL | ~65% | 241 | Alquerque, Battleship, Blackjack, Breakthrough +56 more |
| Nigerian Fulfulde (`fuv`) | EXPERIMENTAL | ~65% | 241 | Alquerque, Bandit, Battleship, Blackjack +56 more |
| Dzongkha (`dzo`) | EXPERIMENTAL | ~63% | 241 | Alquerque, Bandit, Battleship, Blackjack +56 more |
| Nuer (`nus`) | EXPERIMENTAL | ~62% | 241 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Central Aymara (`ayr`) | EXPERIMENTAL | ~66% | 246 | Alquerque, Bandit, Blackjack, Breakthrough +55 more |
| Bambara (`bam`) | EXPERIMENTAL | ~63% | 256 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Kikuyu (`kik`) | EXPERIMENTAL | ~63% | 271 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Sango (`sag`) | EXPERIMENTAL | ~62% | 278 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Bemba (`bem`) | EXPERIMENTAL | ~61% | 283 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Kabyle (`kab`) | EXPERIMENTAL | ~62% | 283 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Akan (`aka`) | EXPERIMENTAL | ~58% | 288 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Kikongo (`kon`) | EXPERIMENTAL | ~62% | 289 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Mossi (`mos`) | EXPERIMENTAL | ~56% | 290 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Southwestern Dinka (`dik`) | EXPERIMENTAL | ~59% | 295 | Alquerque, Bandit, Battleship, Blackjack +56 more |
| Central Atlas Tamazight (`tzm`) | EXPERIMENTAL | ~58% | 298 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Twi (`twi`) | EXPERIMENTAL | ~56% | 317 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Central Kanuri (`knc`) | EXPERIMENTAL | ~55% | 321 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Fon (`fon`) | EXPERIMENTAL | ~56% | 323 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Wolof (`wol`) | EXPERIMENTAL | ~51% | 340 | Bandit, Battleship, Blackjack, Breakthrough +58 more |
| Chokwe (`cjk`) | EXPERIMENTAL | ~53% | 367 | Alquerque, Bandit, Battleship, Blackjack +57 more |
| Tamasheq (`taq`) | EXPERIMENTAL | ~49% | 388 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Dyula (`dyu`) | EXPERIMENTAL | ~46% | 411 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Kabiye (`kbp`) | EXPERIMENTAL | ~42% | 426 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Umbundu (`umb`) | EXPERIMENTAL | ~45% | 428 | Alquerque, Bandit, Battleship, Blackjack +58 more |
| Kimbundu (`kmb`) | EXPERIMENTAL | ~43% | 454 | Alquerque, Bandit, Battleship, Blackjack +59 more |
| Kamba (`kam`) | EXPERIMENTAL | ~41% | 470 | Alquerque, Bandit, Battleship, Blackjack +58 more |

Languages move from experimental to certified as verification improves; the list grows over time.

<!-- END trackb-low-resource -->
