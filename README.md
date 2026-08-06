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

Beyond the human-reviewed languages, TextArena includes **143 additional low-resource UI localizations** produced with open machine translation (NLLB-200) and verified for **meaning fidelity** by an independent **two-model LLM judge** (Llama-3.1-405B + Qwen2.5-72B). Every in-target string is judged by both model families; agreements are auto-confirmed, and a flag from only one family is adjudicated by a careful single-leaf Llama-3.1-405B re-judge (validated at ~100% sensitivity on a human-known control) so the over-flagging model cannot churn faithful strings. Confirmed bugs are re-translated under a no-regression write gate (placeholder / command / curly-slot-multiset parity + language-ID). **These are machine-verified, not native-reviewed.** The **meaning-fidelity %** in the tables is the adjudicated share of in-target strings judged faithful *before* repair (the certification signal); after the repair pass every language — including experimental ones — ships at **≥94%** post-repair fidelity. Per-language post-repair fidelity, residual-bug counts, and target-language coverage are in the machine-readable [`_trackb_confidence.json`](textarena/utils/locales/_trackb_confidence.json). At runtime, `textarena.utils.locales.language_confidence.warn_if_flagged(lang)` emits a `UserWarning` for any non-certified locale.

**Certified-flagged** (132) — adjudicated meaning fidelity ≥85%, sorted best-first:

| Language | Tier | Meaning fidelity | Target-language coverage |
|---|---|---|---|
| Punjabi (`pa`) | CERTIFIED_FLAGGED | 98% | 100% |
| Cebuano (`ceb`) | CERTIFIED_FLAGGED | 97% | 100% |
| Javanese (`jav`) | CERTIFIED_FLAGGED | 97% | 100% |
| Kannada (`kn`) | CERTIFIED_FLAGGED | 97% | 100% |
| Minangkabau (`min`) | CERTIFIED_FLAGGED | 97% | 100% |
| Marathi (`mr`) | CERTIFIED_FLAGGED | 97% | 100% |
| Nepali (`ne`) | CERTIFIED_FLAGGED | 97% | 100% |
| Sindhi (`sd`) | CERTIFIED_FLAGGED | 97% | 100% |
| Sundanese (`sun`) | CERTIFIED_FLAGGED | 97% | 100% |
| Venetian (`vec`) | CERTIFIED_FLAGGED | 97% | 100% |
| Eastern Yiddish (`ydd`) | CERTIFIED_FLAGGED | 97% | 100% |
| Central Kurdish (`ckb`) | CERTIFIED_FLAGGED | 97% | 99% |
| Gujarati (`gu`) | CERTIFIED_FLAGGED | 97% | 99% |
| Maithili (`mai`) | CERTIFIED_FLAGGED | 97% | 99% |
| Telugu (`te`) | CERTIFIED_FLAGGED | 97% | 99% |
| Tajik (`tgk`) | CERTIFIED_FLAGGED | 97% | 99% |
| Assamese (`as`) | CERTIFIED_FLAGGED | 96% | 100% |
| Friulian (`fur`) | CERTIFIED_FLAGGED | 96% | 100% |
| Haitian Creole (`hat`) | CERTIFIED_FLAGGED | 96% | 100% |
| Luxembourgish (`ltz`) | CERTIFIED_FLAGGED | 96% | 100% |
| Pashto (`ps`) | CERTIFIED_FLAGGED | 96% | 100% |
| Zulu (`zu`) | CERTIFIED_FLAGGED | 96% | 100% |
| Balinese (`ban`) | CERTIFIED_FLAGGED | 95% | 100% |
| Esperanto (`epo`) | CERTIFIED_FLAGGED | 95% | 100% |
| Kabyle (`kab`) | CERTIFIED_FLAGGED | 95% | 100% |
| Northern Kurdish (`kmr`) | CERTIFIED_FLAGGED | 95% | 100% |
| Ligurian (`lij`) | CERTIFIED_FLAGGED | 95% | 100% |
| Lombard (`lmo`) | CERTIFIED_FLAGGED | 95% | 100% |
| Magahi (`mag`) | CERTIFIED_FLAGGED | 95% | 100% |
| Maltese (`mlt`) | CERTIFIED_FLAGGED | 95% | 100% |
| Occitan (`oci`) | CERTIFIED_FLAGGED | 95% | 100% |
| Sicilian (`scn`) | CERTIFIED_FLAGGED | 95% | 100% |
| Somali (`so`) | CERTIFIED_FLAGGED | 95% | 100% |
| Waray (`war`) | CERTIFIED_FLAGGED | 95% | 100% |
| Acehnese (`ace`) | CERTIFIED_FLAGGED | 95% | 99% |
| Bashkir (`bak`) | CERTIFIED_FLAGGED | 95% | 99% |
| Bhojpuri (`bho`) | CERTIFIED_FLAGGED | 95% | 99% |
| Malayalam (`ml`) | CERTIFIED_FLAGGED | 95% | 99% |
| Odia (`or`) | CERTIFIED_FLAGGED | 95% | 99% |
| Sardinian (`srd`) | CERTIFIED_FLAGGED | 95% | 99% |
| Chhattisgarhi (`hne`) | CERTIFIED_FLAGGED | 95% | 98% |
| Akan (`aka`) | CERTIFIED_FLAGGED | 94% | 100% |
| Armenian (`hy`) | CERTIFIED_FLAGGED | 94% | 100% |
| Limburgish (`lim`) | CERTIFIED_FLAGGED | 94% | 100% |
| Maori (`mri`) | CERTIFIED_FLAGGED | 94% | 100% |
| Northern Sotho (`nso`) | CERTIFIED_FLAGGED | 94% | 100% |
| Papiamento (`pap`) | CERTIFIED_FLAGGED | 94% | 100% |
| Uzbek (`uz`) | CERTIFIED_FLAGGED | 94% | 100% |
| Ilocano (`ilo`) | CERTIFIED_FLAGGED | 94% | 99% |
| Burmese (`my`) | CERTIFIED_FLAGGED | 94% | 99% |
| Nuer (`nus`) | CERTIFIED_FLAGGED | 94% | 99% |
| Tatar (`tat`) | CERTIFIED_FLAGGED | 94% | 99% |
| Belarusian (`be`) | CERTIFIED_FLAGGED | 93% | 100% |
| Banjar (`bjn`) | CERTIFIED_FLAGGED | 93% | 100% |
| Scottish Gaelic (`gla`) | CERTIFIED_FLAGGED | 93% | 100% |
| Irish (`gle`) | CERTIFIED_FLAGGED | 93% | 100% |
| Kyrgyz (`ky`) | CERTIFIED_FLAGGED | 93% | 100% |
| Lao (`lo`) | CERTIFIED_FLAGGED | 93% | 100% |
| Latgalian (`ltg`) | CERTIFIED_FLAGGED | 93% | 100% |
| Tswana (`tsn`) | CERTIFIED_FLAGGED | 93% | 100% |
| Twi (`twi`) | CERTIFIED_FLAGGED | 93% | 100% |
| Asturian (`ast`) | CERTIFIED_FLAGGED | 93% | 99% |
| Faroese (`fao`) | CERTIFIED_FLAGGED | 93% | 99% |
| Kabuverdianu (`kea`) | CERTIFIED_FLAGGED | 93% | 99% |
| Kazakh (`kk`) | CERTIFIED_FLAGGED | 93% | 99% |
| Dzongkha (`dzo`) | CERTIFIED_FLAGGED | 93% | 98% |
| Santali (`sat`) | CERTIFIED_FLAGGED | 93% | 98% |
| Standard Tibetan (`bod`) | CERTIFIED_FLAGGED | 93% | 96% |
| Egyptian Arabic (`arz`) | CERTIFIED_FLAGGED | 92% | 100% |
| Crimean Tatar (`crh`) | CERTIFIED_FLAGGED | 92% | 100% |
| Igbo (`ig`) | CERTIFIED_FLAGGED | 92% | 100% |
| Shona (`sna`) | CERTIFIED_FLAGGED | 92% | 100% |
| Southern Sotho (`sot`) | CERTIFIED_FLAGGED | 92% | 100% |
| Yoruba (`yo`) | CERTIFIED_FLAGGED | 92% | 100% |
| West Central Oromo (`gaz`) | CERTIFIED_FLAGGED | 92% | 99% |
| Khmer (`km`) | CERTIFIED_FLAGGED | 92% | 99% |
| Sanskrit (`san`) | CERTIFIED_FLAGGED | 92% | 99% |
| Sinhala (`si`) | CERTIFIED_FLAGGED | 92% | 99% |
| Central Atlas Tamazight (`tzm`) | CERTIFIED_FLAGGED | 92% | 99% |
| Ganda (`lug`) | CERTIFIED_FLAGGED | 91% | 100% |
| Malagasy (`mg`) | CERTIFIED_FLAGGED | 91% | 100% |
| Norwegian Nynorsk (`nno`) | CERTIFIED_FLAGGED | 91% | 100% |
| Nyanja (`nya`) | CERTIFIED_FLAGGED | 91% | 100% |
| Wolof (`wol`) | CERTIFIED_FLAGGED | 91% | 100% |
| Xhosa (`xho`) | CERTIFIED_FLAGGED | 91% | 100% |
| Mesopotamian Arabic (`acm`) | CERTIFIED_FLAGGED | 91% | 99% |
| Taizzi-Adeni Arabic (`acq`) | CERTIFIED_FLAGGED | 91% | 99% |
| Najdi Arabic (`ars`) | CERTIFIED_FLAGGED | 91% | 99% |
| Bemba (`bem`) | CERTIFIED_FLAGGED | 91% | 99% |
| Ewe (`ewe`) | CERTIFIED_FLAGGED | 91% | 99% |
| Mizo (`lus`) | CERTIFIED_FLAGGED | 91% | 99% |
| Amharic (`am`) | CERTIFIED_FLAGGED | 91% | 98% |
| Southwestern Dinka (`dik`) | CERTIFIED_FLAGGED | 91% | 98% |
| Tamasheq (`taq`) | CERTIFIED_FLAGGED | 91% | 98% |
| Kikuyu (`kik`) | CERTIFIED_FLAGGED | 91% | 97% |
| Shan (`shn`) | CERTIFIED_FLAGGED | 91% | 96% |
| Tigrinya (`tir`) | CERTIFIED_FLAGGED | 91% | 96% |
| South Levantine Arabic (`ajp`) | CERTIFIED_FLAGGED | 90% | 100% |
| Welsh (`cy`) | CERTIFIED_FLAGGED | 90% | 100% |
| Hausa (`ha`) | CERTIFIED_FLAGGED | 90% | 100% |
| Samoan (`smo`) | CERTIFIED_FLAGGED | 90% | 100% |
| Buginese (`bug`) | CERTIFIED_FLAGGED | 90% | 99% |
| Rundi (`run`) | CERTIFIED_FLAGGED | 90% | 99% |
| Tsonga (`tso`) | CERTIFIED_FLAGGED | 90% | 99% |
| Uyghur (`uig`) | CERTIFIED_FLAGGED | 90% | 99% |
| Dyula (`dyu`) | CERTIFIED_FLAGGED | 90% | 98% |
| Fon (`fon`) | CERTIFIED_FLAGGED | 90% | 98% |
| Jingpho (`kac`) | CERTIFIED_FLAGGED | 90% | 97% |
| North Levantine Arabic (`apc`) | CERTIFIED_FLAGGED | 89% | 100% |
| Fijian (`fij`) | CERTIFIED_FLAGGED | 89% | 100% |
| Nigerian Fulfulde (`fuv`) | CERTIFIED_FLAGGED | 89% | 100% |
| Mongolian (`mn`) | CERTIFIED_FLAGGED | 89% | 100% |
| Swati (`ssw`) | CERTIFIED_FLAGGED | 89% | 100% |
| Silesian (`szl`) | CERTIFIED_FLAGGED | 89% | 100% |
| Moroccan Arabic (`ary`) | CERTIFIED_FLAGGED | 89% | 99% |
| Bambara (`bam`) | CERTIFIED_FLAGGED | 89% | 99% |
| Kamba (`kam`) | CERTIFIED_FLAGGED | 89% | 99% |
| Turkmen (`tuk`) | CERTIFIED_FLAGGED | 89% | 99% |
| Luba-Kasai (`lua`) | CERTIFIED_FLAGGED | 89% | 97% |
| Basque (`eu`) | CERTIFIED_FLAGGED | 88% | 100% |
| Sango (`sag`) | CERTIFIED_FLAGGED | 88% | 100% |
| Tok Pisin (`tpi`) | CERTIFIED_FLAGGED | 88% | 100% |
| Mossi (`mos`) | CERTIFIED_FLAGGED | 88% | 99% |
| Central Kanuri (`knc`) | CERTIFIED_FLAGGED | 88% | 98% |
| Tunisian Arabic (`aeb`) | CERTIFIED_FLAGGED | 87% | 100% |
| Pangasinan (`pag`) | CERTIFIED_FLAGGED | 87% | 100% |
| Awadhi (`awa`) | CERTIFIED_FLAGGED | 87% | 99% |
| Guarani (`grn`) | CERTIFIED_FLAGGED | 87% | 99% |
| South Azerbaijani (`azb`) | CERTIFIED_FLAGGED | 87% | 97% |
| Georgian (`ka`) | CERTIFIED_FLAGGED | 86% | 99% |
| Tumbuka (`tum`) | CERTIFIED_FLAGGED | 85% | 100% |
| Chokwe (`cjk`) | CERTIFIED_FLAGGED | 85% | 78% |

> ⚠️ **Experimental** (11) — raw (pre-repair) meaning fidelity below the 85% certification bar; structurally valid, playable, and repaired to ≥94% post-fix, but the underlying machine translation needed heavy correction. Use for coverage/research, not as a reference translation:

| Language | Tier | Meaning fidelity | Target-language coverage |
|---|---|---|---|
| Lingala (`lin`) | EXPERIMENTAL | 84% | 100% |
| Central Aymara (`ayr`) | EXPERIMENTAL | 84% | 99% |
| Kinyarwanda (`kin`) | EXPERIMENTAL | 84% | 99% |
| Ayacucho Quechua (`quy`) | EXPERIMENTAL | 84% | 99% |
| Luo (`luo`) | EXPERIMENTAL | 83% | 99% |
| Umbundu (`umb`) | EXPERIMENTAL | 83% | 99% |
| Kikongo (`kon`) | EXPERIMENTAL | 82% | 98% |
| Kabiye (`kbp`) | EXPERIMENTAL | 81% | 97% |
| Kimbundu (`kmb`) | EXPERIMENTAL | 80% | 99% |
| Kashmiri (`kas`) | EXPERIMENTAL | 70% | 98% |
| Meitei (`mni`) | EXPERIMENTAL | 67% | 94% |

Languages move from experimental to certified as verification improves; the list grows over time.

<!-- END trackb-low-resource -->
