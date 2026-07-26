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

Beyond the human-reviewed languages, TextArena includes **143 additional low-resource UI localizations** produced with open machine translation (NLLB-200) and verified for **meaning fidelity** by a careful two-model LLM judge (llama-3.1-405B + Qwen2.5-72B, per-leaf concordance) — validated at 100% sensitivity/specificity on a human-known control. **These are machine-verified, not native-reviewed.** Each language lists its measured **meaning-fidelity %** (share of sampled strings both judges rate faithful) and its target-language coverage. At runtime, `textarena.utils.locales.language_confidence.warn_if_flagged(lang)` emits a `UserWarning` for any non-certified locale; the machine-readable source is [`_trackb_confidence.json`](textarena/utils/locales/_trackb_confidence.json).

**Certified-flagged** (124) — LLM-verified meaning fidelity, sorted best-first:

| Language | Tier | Meaning fidelity | Target-language coverage |
|---|---|---|---|
| Kannada (`kn`) | CERTIFIED_FLAGGED | 100% | ~95% |
| Gujarati (`gu`) | CERTIFIED_FLAGGED | 100% | ~96% |
| Punjabi (`pa`) | CERTIFIED_FLAGGED | 100% | ~97% |
| Marathi (`mr`) | CERTIFIED_FLAGGED | 100% | ~97% |
| Sindhi (`sd`) | CERTIFIED_FLAGGED | 100% | ~96% |
| Lao (`lo`) | CERTIFIED_FLAGGED | 100% | ~95% |
| Uzbek (`uz`) | CERTIFIED_FLAGGED | 100% | ~95% |
| Malayalam (`ml`) | CERTIFIED_FLAGGED | 100% | ~95% |
| Assamese (`as`) | CERTIFIED_FLAGGED | 100% | ~95% |
| Odia (`or`) | CERTIFIED_FLAGGED | 100% | ~94% |
| Yoruba (`yo`) | CERTIFIED_FLAGGED | 100% | ~93% |
| Banjar (`bjn`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Egyptian Arabic (`arz`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Crimean Tatar (`crh`) | CERTIFIED_FLAGGED | 100% | ~90% |
| Acehnese (`ace`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Moroccan Arabic (`ary`) | CERTIFIED_FLAGGED | 100% | ~91% |
| Central Kurdish (`ckb`) | CERTIFIED_FLAGGED | 100% | ~86% |
| Bashkir (`bak`) | CERTIFIED_FLAGGED | 100% | ~82% |
| Esperanto (`epo`) | CERTIFIED_FLAGGED | 100% | ~94% |
| Irish (`gle`) | CERTIFIED_FLAGGED | 100% | ~89% |
| Javanese (`jav`) | CERTIFIED_FLAGGED | 100% | ~93% |
| Lombard (`lmo`) | CERTIFIED_FLAGGED | 100% | ~88% |
| Luxembourgish (`ltz`) | CERTIFIED_FLAGGED | 100% | ~90% |
| Chhattisgarhi (`hne`) | CERTIFIED_FLAGGED | 100% | ~88% |
| Maithili (`mai`) | CERTIFIED_FLAGGED | 100% | ~91% |
| Magahi (`mag`) | CERTIFIED_FLAGGED | 100% | ~88% |
| Ilocano (`ilo`) | CERTIFIED_FLAGGED | 100% | ~89% |
| Ligurian (`lij`) | CERTIFIED_FLAGGED | 100% | ~87% |
| Sicilian (`scn`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Papiamento (`pap`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Occitan (`oci`) | CERTIFIED_FLAGGED | 100% | ~91% |
| Minangkabau (`min`) | CERTIFIED_FLAGGED | 100% | ~90% |
| Sardinian (`srd`) | CERTIFIED_FLAGGED | 100% | ~88% |
| Maori (`mri`) | CERTIFIED_FLAGGED | 100% | ~90% |
| Maltese (`mlt`) | CERTIFIED_FLAGGED | 100% | ~86% |
| Tatar (`tat`) | CERTIFIED_FLAGGED | 100% | ~86% |
| Venetian (`vec`) | CERTIFIED_FLAGGED | 100% | ~92% |
| Tajik (`tgk`) | CERTIFIED_FLAGGED | 100% | ~90% |
| Xhosa (`xho`) | CERTIFIED_FLAGGED | 100% | ~86% |
| Turkmen (`tuk`) | CERTIFIED_FLAGGED | 100% | ~86% |
| Belarusian (`be`) | CERTIFIED_FLAGGED | 98% | ~96% |
| Pashto (`ps`) | CERTIFIED_FLAGGED | 98% | ~95% |
| Telugu (`te`) | CERTIFIED_FLAGGED | 98% | ~95% |
| Zulu (`zu`) | CERTIFIED_FLAGGED | 98% | ~95% |
| Kazakh (`kk`) | CERTIFIED_FLAGGED | 98% | ~93% |
| Kyrgyz (`ky`) | CERTIFIED_FLAGGED | 98% | ~94% |
| Hausa (`ha`) | CERTIFIED_FLAGGED | 98% | ~95% |
| Igbo (`ig`) | CERTIFIED_FLAGGED | 98% | ~96% |
| Mongolian (`mn`) | CERTIFIED_FLAGGED | 98% | ~90% |
| Amharic (`am`) | CERTIFIED_FLAGGED | 98% | ~85% |
| ceb (`ceb`) | CERTIFIED_FLAGGED | 98% | ~91% |
| Najdi Arabic (`ars`) | CERTIFIED_FLAGGED | 98% | ~93% |
| North Levantine Arabic (`apc`) | CERTIFIED_FLAGGED | 98% | ~91% |
| South Levantine Arabic (`ajp`) | CERTIFIED_FLAGGED | 98% | ~92% |
| Bhojpuri (`bho`) | CERTIFIED_FLAGGED | 98% | ~88% |
| Asturian (`ast`) | CERTIFIED_FLAGGED | 98% | ~84% |
| Balinese (`ban`) | CERTIFIED_FLAGGED | 98% | ~91% |
| Awadhi (`awa`) | CERTIFIED_FLAGGED | 98% | ~89% |
| Akan (`aka`) | CERTIFIED_FLAGGED | 98% | ~74% |
| Scottish Gaelic (`gla`) | CERTIFIED_FLAGGED | 98% | ~88% |
| Friulian (`fur`) | CERTIFIED_FLAGGED | 98% | ~88% |
| Faroese (`fao`) | CERTIFIED_FLAGGED | 98% | ~91% |
| Dzongkha (`dzo`) | CERTIFIED_FLAGGED | 98% | ~75% |
| Haitian Creole (`hat`) | CERTIFIED_FLAGGED | 98% | ~93% |
| Northern Kurdish (`kmr`) | CERTIFIED_FLAGGED | 98% | ~87% |
| Mizo (`lus`) | CERTIFIED_FLAGGED | 98% | ~78% |
| Jingpho (`kac`) | CERTIFIED_FLAGGED | 98% | ~71% |
| Shona (`sna`) | CERTIFIED_FLAGGED | 98% | ~90% |
| Samoan (`smo`) | CERTIFIED_FLAGGED | 98% | ~89% |
| Silesian (`szl`) | CERTIFIED_FLAGGED | 98% | ~91% |
| Sanskrit (`san`) | CERTIFIED_FLAGGED | 98% | ~86% |
| Shan (`shn`) | CERTIFIED_FLAGGED | 98% | ~76% |
| Tamasheq (`taq`) | CERTIFIED_FLAGGED | 98% | ~71% |
| Eastern Yiddish (`ydd`) | CERTIFIED_FLAGGED | 98% | ~88% |
| Waray (`war`) | CERTIFIED_FLAGGED | 98% | ~87% |
| Central Atlas Tamazight (`tzm`) | CERTIFIED_FLAGGED | 98% | ~76% |
| Nepali (`ne`) | CERTIFIED_FLAGGED | 95% | ~95% |
| Khmer (`km`) | CERTIFIED_FLAGGED | 95% | ~94% |
| Armenian (`hy`) | CERTIFIED_FLAGGED | 95% | ~95% |
| Welsh (`cy`) | CERTIFIED_FLAGGED | 95% | ~93% |
| Sinhala (`si`) | CERTIFIED_FLAGGED | 95% | ~94% |
| Burmese (`my`) | CERTIFIED_FLAGGED | 95% | ~94% |
| Malagasy (`mg`) | CERTIFIED_FLAGGED | 95% | ~94% |
| Georgian (`ka`) | CERTIFIED_FLAGGED | 95% | ~91% |
| Taizzi-Adeni Arabic (`acq`) | CERTIFIED_FLAGGED | 95% | ~92% |
| Mesopotamian Arabic (`acm`) | CERTIFIED_FLAGGED | 95% | ~92% |
| South Azerbaijani (`azb`) | CERTIFIED_FLAGGED | 95% | ~82% |
| Standard Tibetan (`bod`) | CERTIFIED_FLAGGED | 95% | ~75% |
| Limburgish (`lim`) | CERTIFIED_FLAGGED | 95% | ~91% |
| Latgalian (`ltg`) | CERTIFIED_FLAGGED | 95% | ~87% |
| Kabuverdianu (`kea`) | CERTIFIED_FLAGGED | 95% | ~87% |
| Sundanese (`sun`) | CERTIFIED_FLAGGED | 95% | ~94% |
| Tigrinya (`tir`) | CERTIFIED_FLAGGED | 95% | ~78% |
| Tsonga (`tso`) | CERTIFIED_FLAGGED | 95% | ~88% |
| Wolof (`wol`) | CERTIFIED_FLAGGED | 95% | ~70% |
| Somali (`so`) | CERTIFIED_FLAGGED | 92% | ~95% |
| Central Aymara (`ayr`) | CERTIFIED_FLAGGED | 92% | ~79% |
| Nigerian Fulfulde (`fuv`) | CERTIFIED_FLAGGED | 92% | ~81% |
| Kinyarwanda (`kin`) | CERTIFIED_FLAGGED | 92% | ~86% |
| Ganda (`lug`) | CERTIFIED_FLAGGED | 92% | ~84% |
| Luo (`luo`) | CERTIFIED_FLAGGED | 92% | ~84% |
| Central Kanuri (`knc`) | CERTIFIED_FLAGGED | 92% | ~76% |
| Norwegian Nynorsk (`nno`) | CERTIFIED_FLAGGED | 92% | ~89% |
| Swati (`ssw`) | CERTIFIED_FLAGGED | 92% | ~87% |
| Mossi (`mos`) | CERTIFIED_FLAGGED | 92% | ~71% |
| Uyghur (`uig`) | CERTIFIED_FLAGGED | 92% | ~82% |
| Tswana (`tsn`) | CERTIFIED_FLAGGED | 92% | ~86% |
| Twi (`twi`) | CERTIFIED_FLAGGED | 92% | ~76% |
| Basque (`eu`) | CERTIFIED_FLAGGED | 90% | ~86% |
| Tunisian Arabic (`aeb`) | CERTIFIED_FLAGGED | 90% | ~90% |
| Fijian (`fij`) | CERTIFIED_FLAGGED | 90% | ~84% |
| Guarani (`grn`) | CERTIFIED_FLAGGED | 90% | ~84% |
| Ewe (`ewe`) | CERTIFIED_FLAGGED | 90% | ~79% |
| Fon (`fon`) | CERTIFIED_FLAGGED | 90% | ~74% |
| Kabyle (`kab`) | CERTIFIED_FLAGGED | 90% | ~80% |
| Ayacucho Quechua (`quy`) | CERTIFIED_FLAGGED | 90% | ~79% |
| Tok Pisin (`tpi`) | CERTIFIED_FLAGGED | 90% | ~84% |
| Kashmiri (`kas`) | CERTIFIED_FLAGGED | 88% | ~84% |
| Pangasinan (`pag`) | CERTIFIED_FLAGGED | 88% | ~86% |
| Northern Sotho (`nso`) | CERTIFIED_FLAGGED | 88% | ~85% |
| Nuer (`nus`) | CERTIFIED_FLAGGED | 88% | ~79% |
| Bemba (`bem`) | CERTIFIED_FLAGGED | 85% | ~78% |
| Southwestern Dinka (`dik`) | CERTIFIED_FLAGGED | 85% | ~78% |
| Southern Sotho (`sot`) | CERTIFIED_FLAGGED | 85% | ~89% |

> ⚠️ **Experimental** (19) — measured meaning fidelity below the certification bar; structurally valid and playable, but prose quality is lower. Use for coverage/research, not as a reference translation:

| Language | Tier | Meaning fidelity | Target-language coverage |
|---|---|---|---|
| Dyula (`dyu`) | EXPERIMENTAL | 82% | ~68% |
| Nyanja (`nya`) | EXPERIMENTAL | 82% | ~90% |
| Sango (`sag`) | EXPERIMENTAL | 82% | ~77% |
| Buginese (`bug`) | EXPERIMENTAL | 80% | ~86% |
| Bambara (`bam`) | EXPERIMENTAL | 80% | ~79% |
| Lingala (`lin`) | EXPERIMENTAL | 80% | ~85% |
| Kikongo (`kon`) | EXPERIMENTAL | 80% | ~76% |
| Kamba (`kam`) | EXPERIMENTAL | 80% | ~57% |
| Rundi (`run`) | EXPERIMENTAL | 80% | ~86% |
| Santali (`sat`) | EXPERIMENTAL | 80% | ~75% |
| Kikuyu (`kik`) | EXPERIMENTAL | 78% | ~79% |
| Kabiye (`kbp`) | EXPERIMENTAL | 78% | ~64% |
| Meitei (`mni`) | EXPERIMENTAL | 78% | ~69% |
| West Central Oromo (`gaz`) | EXPERIMENTAL | 75% | ~79% |
| Tumbuka (`tum`) | EXPERIMENTAL | 72% | ~82% |
| Umbundu (`umb`) | EXPERIMENTAL | 72% | ~63% |
| Kimbundu (`kmb`) | EXPERIMENTAL | 70% | ~63% |
| Luba-Kasai (`lua`) | EXPERIMENTAL | 65% | ~82% |
| Chokwe (`cjk`) | EXPERIMENTAL | 63% | ~63% |

Languages move from experimental to certified as verification improves; the list grows over time.

<!-- END trackb-low-resource -->
