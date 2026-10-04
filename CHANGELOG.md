# Changelog

## 1.0.0

TextArena 1.0 rebuilds the library around a single game engine, `ta.GameEnv`, with one set of rules for actions,
observations, rewards, invalid moves, seeding, and replays shared by all 108 games. Every game was audited, and many
rules and rewards were corrected along the way, so every environment id moved to version 1 (`-v1`). Scores from
`-v0` environments are not comparable with `-v1` scores.

### Highlights

- **One engine.** A game declares its settings as `ta.Param`s and implements `setup`, `prompt`, and `apply`; the
  engine handles turns, invalid moves, eliminations, turn limits, rewards, observation routing, and validation.
- **Two views of every configuration.** `Game-v1` shows only the messages since the player's last turn;
  `Game-v1-mdp` puts everything needed to act into every observation.
- **Bare actions.** Games take moves such as `e2e4` or `bid 3 5s`. Models put their move inside
  `<action>...</action>` tags, and `ta.extract_action` extracts it.
- **Replays.** `env.record()` returns a JSON-serializable record of a game, and `ta.replay(record)` rebuilds it,
  including the answers of LLM judges.
- **No required dependencies.** `pip install textarena` installs only the games; the `agents`, `render`,
  `translations`, and `all` extras add model agents, the terminal renderer, and translations.
- **Translations** into 192 languages ship as the separate `textarena-locales` package.
- **Self-contained games.** Each game folder holds its code, registration, tests, and README, and is picked up
  automatically.
- **Conformance suite.** Every game is checked for termination, reward shape, determinism, observation routing,
  rejected moves leaving the game unchanged, snapshot and replay round trips, long pathological inputs, and Python's
  global random state.

### Migrating from 0.x

**Environment ids.** Replace `-v0` with `-v1`; `ta.make` names the replacement when given a retired id. The registry
keeps a few configurations per game (141 instead of 262); every other setting is a keyword argument away, for
example `ta.make("PigDice-v1", winning_score=50)`. Each game's README lists its parameters and accepted values.

**Game loop.** `env.step(action)` returns only whether the game is over:

```python
done = env.step(action)          # was: done, info = env.step(action)
```

`env.reset()` may omit `num_players` for games with a fixed or default player count, and raises `ValueError` for an
unsupported count. Without a seed, a random one is drawn and recorded so the game can be replayed.

**Installation.** Model agents need `pip install "textarena[agents]"`, `SimpleRenderWrapper` needs `"textarena[render]"`,
and `TranslationWrapper` needs `"textarena[translations]"`. `requirements.txt` is gone.

**Removed and renamed APIs.**

| 0.x | 1.0 |
| --- | --- |
| `done, info = env.step(action)` | `done = env.step(action)` |
| `register_with_versions(...)` | `register(...)`, called from the game's own `__init__.py` |
| `ta.make([id_a, id_b])` (random choice) | choose the id yourself |
| `BoardObservationWrapper`, `FullHistoryObservationWrapper` | `MDPObservationWrapper` (games set `mdp_includes_actions`) |
| `RenderWrapper`, `ActionWrapper`, `AgentWrapper` | removed |
| `pprint_registry_detailed`, `check_env_exists` | `textarena.envs.registration.ENV_REGISTRY` |
| `make_online`, `make_mgc_online` | removed (no online play) |
| `textarena.envs.utils` | `textarena.utils` |
| BabyAiText | removed |

**Game parameters** are keyword-only and validated when the environment is made; a value of the wrong type or out
of range raises `ValueError`, and an unknown name raises `TypeError`. Renamed or removed parameters:

| Game | 0.x | 1.0 |
| --- | --- | --- |
| UltimateTexasHoldem | `max_turns` (counted rounds) | `max_rounds` |
| Diplomacy | `max_turns` (counted game years) | `max_game_years` |
| PublicGoodsGame | `num_players` | `default_num_players` |
| VendorNegotiation | `brand_target_percentage`, `vendor_baseline_multiplier` | `brand_target_fraction`, `vendor_target_fraction` |
| Klondike, VendorNegotiation | constructor `seed` | `env.reset(seed=...)` |
| Sokoban | `env.reset(..., max_retries=...)` | `max_retries` parameter |
| Bohnanza, NewRecruit, Santorini, ScorableGames, TwoDollar, VendorNegotiation, WinAsMuchAsYouCan | `error_allowance` | removed (every game allows one retry) |

### Rule and reward changes

- **Rewards** use one scale per kind of game: `+1` win, `-1` loss, `0` draw in competitive games; `0` to `1` in
  single-player games (failing or quitting scores `0`); and each player's own score from `0` to `1` in cooperative
  and mixed-motive games. Klondike now scores cards on the foundations divided by 52, Set the Sets found divided by
  the turns, Bandit `1` for the best button and `0` otherwise, and UltimateTexasHoldem `1` or `0`.
- **Invalid moves**: every game warns once and escalates on the second invalid move in a row.
- **PublicGoodsGame** rewards each player's own payoff (scaled to `0` to `1`) instead of ranking players, which
  restores the social dilemma: the lowest contributor no longer always wins.
- **VendorNegotiation** scores each side `1` when the deal meets its own target, so a deal meeting both targets beats
  no deal. **UsedCarNegotiation** keeps its surplus-share rewards.
- **LeTruc**: only the player who accepted the last raise may raise next. **Golf**: a 2 scores −2 (a pair in a
  column still scores 0). **Briscola**: four players play as two partnerships, and an invalid-move forfeit loses for
  the team. **QuantumTicTacToe**: the opponent of the player who closes a cycle chooses its collapse.
  **SpiteAndMalice**: cleared center piles are shuffled back into the draw pile, the higher pay-off card starts, and
  only a position where nobody can ever move again ends the game early. **RetroSpaceDuel**: the first mover is drawn
  at random. **SpellingBee**: a 50-turn limit ends in a draw.
- **LLM juries and game masters** (Debate, ScenarioPlanning, GuessWho, TwentyQuestions) use `qwen/qwen3.8-27b`.
- **Word games** check words against frozen English word lists, identical on every machine, and never draw offensive
  words as secrets. Chess uses its own rules engine instead of python-chess.
- Many other fixes from a full audit of every game; see each game's README for its exact rules.
