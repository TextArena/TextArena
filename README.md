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

**Certified-flagged** (111) — verified; a few games flagged:

| Language | Tier | Translated coverage | Confirmed (reverted) | Flagged games |
|---|---|---|---|---|
| Kannada (`kn`) | CERTIFIED_FLAGGED | ~95% | 0 | — |
| Gujarati (`gu`) | CERTIFIED_FLAGGED | ~96% | 0 | — |
| Punjabi (`pa`) | CERTIFIED_FLAGGED | ~97% | 0 | — |
| Marathi (`mr`) | CERTIFIED_FLAGGED | ~97% | 0 | — |
| Lao (`lo`) | CERTIFIED_FLAGGED | ~95% | 0 | — |
| Central Kurdish (`ckb`) | CERTIFIED_FLAGGED | ~86% | 0 | — |
| Sindhi (`sd`) | CERTIFIED_FLAGGED | ~96% | 1 | — |
| Nepali (`ne`) | CERTIFIED_FLAGGED | ~95% | 1 | — |
| Amharic (`am`) | CERTIFIED_FLAGGED | ~85% | 1 | — |
| Chhattisgarhi (`hne`) | CERTIFIED_FLAGGED | ~88% | 1 | — |
| Maithili (`mai`) | CERTIFIED_FLAGGED | ~91% | 1 | — |
| Ilocano (`ilo`) | CERTIFIED_FLAGGED | ~89% | 1 | — |
| Kashmiri (`kas`) | CERTIFIED_FLAGGED | ~84% | 1 | — |
| Kikuyu (`kik`) | CERTIFIED_FLAGGED | ~79% | 1 | — |
| Sundanese (`sun`) | CERTIFIED_FLAGGED | ~94% | 1 | — |
| Tigrinya (`tir`) | CERTIFIED_FLAGGED | ~78% | 1 | — |
| ceb (`ceb`) | CERTIFIED_FLAGGED | ~91% | 2 | — |
| Banjar (`bjn`) | CERTIFIED_FLAGGED | ~92% | 2 | — |
| Najdi Arabic (`ars`) | CERTIFIED_FLAGGED | ~93% | 2 | — |
| Egyptian Arabic (`arz`) | CERTIFIED_FLAGGED | ~92% | 2 | — |
| Esperanto (`epo`) | CERTIFIED_FLAGGED | ~94% | 2 | — |
| Scottish Gaelic (`gla`) | CERTIFIED_FLAGGED | ~88% | 2 | — |
| Irish (`gle`) | CERTIFIED_FLAGGED | ~89% | 2 | — |
| Javanese (`jav`) | CERTIFIED_FLAGGED | ~93% | 2 | — |
| Latgalian (`ltg`) | CERTIFIED_FLAGGED | ~87% | 2 | — |
| Luo (`luo`) | CERTIFIED_FLAGGED | ~84% | 2 | — |
| Central Kanuri (`knc`) | CERTIFIED_FLAGGED | ~76% | 2 | — |
| Southern Sotho (`sot`) | CERTIFIED_FLAGGED | ~89% | 2 | — |
| Minangkabau (`min`) | CERTIFIED_FLAGGED | ~90% | 2 | — |
| Nyanja (`nya`) | CERTIFIED_FLAGGED | ~90% | 2 | — |
| Shona (`sna`) | CERTIFIED_FLAGGED | ~90% | 2 | — |
| Samoan (`smo`) | CERTIFIED_FLAGGED | ~89% | 2 | — |
| Maori (`mri`) | CERTIFIED_FLAGGED | ~90% | 2 | — |
| Pangasinan (`pag`) | CERTIFIED_FLAGGED | ~86% | 2 | — |
| Meitei (`mni`) | CERTIFIED_FLAGGED | ~69% | 2 | — |
| Swati (`ssw`) | CERTIFIED_FLAGGED | ~87% | 2 | — |
| Sanskrit (`san`) | CERTIFIED_FLAGGED | ~86% | 2 | — |
| Belarusian (`be`) | CERTIFIED_FLAGGED | ~96% | 3 | — |
| Uzbek (`uz`) | CERTIFIED_FLAGGED | ~95% | 3 | — |
| Malayalam (`ml`) | CERTIFIED_FLAGGED | ~95% | 3 | — |
| Welsh (`cy`) | CERTIFIED_FLAGGED | ~93% | 3 | — |
| Burmese (`my`) | CERTIFIED_FLAGGED | ~94% | 3 | — |
| Somali (`so`) | CERTIFIED_FLAGGED | ~95% | 3 | — |
| Hausa (`ha`) | CERTIFIED_FLAGGED | ~95% | 3 | — |
| Taizzi-Adeni Arabic (`acq`) | CERTIFIED_FLAGGED | ~92% | 3 | — |
| Acehnese (`ace`) | CERTIFIED_FLAGGED | ~92% | 3 | — |
| West Central Oromo (`gaz`) | CERTIFIED_FLAGGED | ~79% | 3 | — |
| Nigerian Fulfulde (`fuv`) | CERTIFIED_FLAGGED | ~81% | 3 | — |
| Haitian Creole (`hat`) | CERTIFIED_FLAGGED | ~93% | 3 | — |
| Northern Kurdish (`kmr`) | CERTIFIED_FLAGGED | ~87% | 3 | — |
| Tatar (`tat`) | CERTIFIED_FLAGGED | ~86% | 3 | — |
| Rundi (`run`) | CERTIFIED_FLAGGED | ~86% | 3 | — |
| Tajik (`tgk`) | CERTIFIED_FLAGGED | ~90% | 3 | — |
| Tsonga (`tso`) | CERTIFIED_FLAGGED | ~88% | 3 | — |
| Armenian (`hy`) | CERTIFIED_FLAGGED | ~95% | 4 | — |
| Igbo (`ig`) | CERTIFIED_FLAGGED | ~96% | 4 | — |
| South Azerbaijani (`azb`) | CERTIFIED_FLAGGED | ~82% | 4 | — |
| Limburgish (`lim`) | CERTIFIED_FLAGGED | ~91% | 4 | — |
| Tamasheq (`taq`) | CERTIFIED_FLAGGED | ~71% | 4 | — |
| Crimean Tatar (`crh`) | CERTIFIED_FLAGGED | ~90% | 5 | — |
| South Levantine Arabic (`ajp`) | CERTIFIED_FLAGGED | ~92% | 5 | — |
| Moroccan Arabic (`ary`) | CERTIFIED_FLAGGED | ~91% | 5 | — |
| Bashkir (`bak`) | CERTIFIED_FLAGGED | ~82% | 5 | — |
| Guarani (`grn`) | CERTIFIED_FLAGGED | ~84% | 5 | — |
| Southwestern Dinka (`dik`) | CERTIFIED_FLAGGED | ~78% | 5 | — |
| Lombard (`lmo`) | CERTIFIED_FLAGGED | ~88% | 5 | — |
| Luxembourgish (`ltz`) | CERTIFIED_FLAGGED | ~90% | 5 | — |
| Northern Sotho (`nso`) | CERTIFIED_FLAGGED | ~85% | 5 | — |
| Tswana (`tsn`) | CERTIFIED_FLAGGED | ~86% | 5 | — |
| Central Atlas Tamazight (`tzm`) | CERTIFIED_FLAGGED | ~76% | 5 | — |
| Telugu (`te`) | CERTIFIED_FLAGGED | ~95% | 6 | — |
| Sinhala (`si`) | CERTIFIED_FLAGGED | ~94% | 6 | — |
| Mesopotamian Arabic (`acm`) | CERTIFIED_FLAGGED | ~92% | 6 | — |
| Buginese (`bug`) | CERTIFIED_FLAGGED | ~86% | 6 | — |
| Bambara (`bam`) | CERTIFIED_FLAGGED | ~79% | 6 | — |
| Akan (`aka`) | CERTIFIED_FLAGGED | ~74% | 6 | — |
| Mizo (`lus`) | CERTIFIED_FLAGGED | ~78% | 6 | — |
| Sicilian (`scn`) | CERTIFIED_FLAGGED | ~92% | 6 | — |
| Occitan (`oci`) | CERTIFIED_FLAGGED | ~91% | 6 | — |
| Maltese (`mlt`) | CERTIFIED_FLAGGED | ~86% | 6 | — |
| Nuer (`nus`) | CERTIFIED_FLAGGED | ~79% | 6 | — |
| Sango (`sag`) | CERTIFIED_FLAGGED | ~77% | 6 | — |
| Xhosa (`xho`) | CERTIFIED_FLAGGED | ~86% | 6 | — |
| Turkmen (`tuk`) | CERTIFIED_FLAGGED | ~86% | 6 | — |
| Central Aymara (`ayr`) | CERTIFIED_FLAGGED | ~79% | 7 | — |
| Balinese (`ban`) | CERTIFIED_FLAGGED | ~91% | 7 | — |
| Faroese (`fao`) | CERTIFIED_FLAGGED | ~91% | 7 | — |
| Ligurian (`lij`) | CERTIFIED_FLAGGED | ~87% | 7 | — |
| Kabyle (`kab`) | CERTIFIED_FLAGGED | ~80% | 7 | — |
| Silesian (`szl`) | CERTIFIED_FLAGGED | ~91% | 7 | — |
| Venetian (`vec`) | CERTIFIED_FLAGGED | ~92% | 7 | — |
| Twi (`twi`) | CERTIFIED_FLAGGED | ~76% | 7 | — |
| Pashto (`ps`) | CERTIFIED_FLAGGED | ~95% | 8 | — |
| Zulu (`zu`) | CERTIFIED_FLAGGED | ~95% | 8 | — |
| Assamese (`as`) | CERTIFIED_FLAGGED | ~95% | 8 | — |
| Malagasy (`mg`) | CERTIFIED_FLAGGED | ~94% | 8 | — |
| Fijian (`fij`) | CERTIFIED_FLAGGED | ~84% | 8 | — |
| Papiamento (`pap`) | CERTIFIED_FLAGGED | ~92% | 8 | — |
| Eastern Yiddish (`ydd`) | CERTIFIED_FLAGGED | ~88% | 8 | — |
| Khmer (`km`) | CERTIFIED_FLAGGED | ~94% | 9 | — |
| North Levantine Arabic (`apc`) | CERTIFIED_FLAGGED | ~91% | 9 | — |
| Ewe (`ewe`) | CERTIFIED_FLAGGED | ~79% | 9 | — |
| Ganda (`lug`) | CERTIFIED_FLAGGED | ~84% | 9 | — |
| Shan (`shn`) | CERTIFIED_FLAGGED | ~76% | 9 | — |
| Waray (`war`) | CERTIFIED_FLAGGED | ~87% | 9 | — |
| Odia (`or`) | CERTIFIED_FLAGGED | ~94% | 10 | — |
| Yoruba (`yo`) | CERTIFIED_FLAGGED | ~93% | 10 | — |
| Asturian (`ast`) | CERTIFIED_FLAGGED | ~84% | 10 | — |
| Friulian (`fur`) | CERTIFIED_FLAGGED | ~88% | 10 | — |
| Santali (`sat`) | CERTIFIED_FLAGGED | ~75% | 10 | — |
| Uyghur (`uig`) | CERTIFIED_FLAGGED | ~82% | 10 | — |

> ⚠️ **Experimental** (32) — structurally valid and playable, but the prose is **not certified** and likely contains further errors the verifier missed. Use for coverage/research, not as a reference translation:

| Language | Tier | Translated coverage | Confirmed (reverted) | Flagged games |
|---|---|---|---|---|
| Kyrgyz (`ky`) | EXPERIMENTAL | ~94% | 11 | — |
| Mongolian (`mn`) | EXPERIMENTAL | ~90% | 11 | — |
| Tunisian Arabic (`aeb`) | EXPERIMENTAL | ~90% | 11 | — |
| Kabuverdianu (`kea`) | EXPERIMENTAL | ~87% | 11 | — |
| Luba-Kasai (`lua`) | EXPERIMENTAL | ~82% | 11 | — |
| Jingpho (`kac`) | EXPERIMENTAL | ~71% | 11 | — |
| Dzongkha (`dzo`) | EXPERIMENTAL | ~75% | 12 | — |
| Sardinian (`srd`) | EXPERIMENTAL | ~88% | 12 | — |
| Wolof (`wol`) | EXPERIMENTAL | ~70% | 12 | — |
| Standard Tibetan (`bod`) | EXPERIMENTAL | ~75% | 13 | — |
| Magahi (`mag`) | EXPERIMENTAL | ~88% | 13 | — |
| Lingala (`lin`) | EXPERIMENTAL | ~85% | 13 | — |
| Bhojpuri (`bho`) | EXPERIMENTAL | ~88% | 14 | — |
| Bemba (`bem`) | EXPERIMENTAL | ~78% | 14 | — |
| Kikongo (`kon`) | EXPERIMENTAL | ~76% | 14 | — |
| Kinyarwanda (`kin`) | EXPERIMENTAL | ~86% | 15 | — |
| Mossi (`mos`) | EXPERIMENTAL | ~71% | 15 | — |
| Kazakh (`kk`) | EXPERIMENTAL | ~93% | 16 | — |
| Ayacucho Quechua (`quy`) | EXPERIMENTAL | ~79% | 16 | — |
| Tok Pisin (`tpi`) | EXPERIMENTAL | ~84% | 17 | — |
| Tumbuka (`tum`) | EXPERIMENTAL | ~82% | 18 | — |
| Kabiye (`kbp`) | EXPERIMENTAL | ~64% | 19 | — |
| Norwegian Nynorsk (`nno`) | EXPERIMENTAL | ~89% | 19 | — |
| Dyula (`dyu`) | EXPERIMENTAL | ~68% | 21 | — |
| Fon (`fon`) | EXPERIMENTAL | ~74% | 23 | — |
| Awadhi (`awa`) | EXPERIMENTAL | ~89% | 24 | — |
| Kimbundu (`kmb`) | EXPERIMENTAL | ~63% | 29 | — |
| Georgian (`ka`) | EXPERIMENTAL | ~91% | 33 | — |
| Basque (`eu`) | EXPERIMENTAL | ~86% | 35 | — |
| Umbundu (`umb`) | EXPERIMENTAL | ~63% | 37 | — |
| Kamba (`kam`) | EXPERIMENTAL | ~57% | 75 | — |
| Chokwe (`cjk`) | EXPERIMENTAL | ~63% | 112 | — |

Languages move from experimental to certified as verification improves; the list grows over time.

<!-- END trackb-low-resource -->
