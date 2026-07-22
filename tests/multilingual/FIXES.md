# Pre-existing bugs surfaced during localization

This branch's main purpose is multilingual support, but converting each game (and
running `scripts/check_locales.py`) surfaced pre-existing bugs unrelated to
translation. They are fixed here and logged separately so reviewers can see what
is a **behavior fix** vs. what is **new localization**. Each fix is behavior-only
where possible; where a fix necessarily changes output, it is called out.

| # | Game | Bug | Fix | Behavior change? |
|---|------|-----|-----|------------------|
| 1 | ReverseTicTacToe | `_render_board` used a Python 3.12+ nested same-quote f-string (`f"…{d["board"]}…"`), a `SyntaxError` on Python 3.10/3.11 — the env could not be imported at all, despite `requires-python >=3.10`. | Swapped inner quotes to single quotes. | No — output identical, file now imports on 3.10/3.11. |
| 2 | Nim | `_render_piles` was orphaned by the multilingual refactor and half-converted to a nonexistent locale key `state.pile`; it would `KeyError` if ever called. The refactor had also replaced dynamic board rendering with a template hardcoding exactly 3 piles (breaks custom pile counts). | Restored the original dynamic `_render_piles`, wrapped by the localized `Current Pile:` header via a single `{piles}` slot. | English output byte-identical to `main`; custom pile counts work again. |
| 3 | IteratedStagHunt | Same Python 3.12+ nested same-quote f-string bug as #1 (in the round-results message). **Not yet fixed** — this is a shared-language communication game, deferred from this PR. | — (flagged for the communication-games track) | — |
| 4 | Cryptarithm | Two argument-order bugs: (a) all four `set_invalid_move(...)` calls pass args swapped — signature is `set_invalid_move(reason, reward=-1.0)` but the game calls `set_invalid_move(self._progress(), "<message>")`, so the invalid-move *reason* shown was a progress float ("Reason: 0.0") and the message was misfiled as the reward; (b) the player-action echo calls `add_observation(pid, action, PLAYER_ACTION)` positionally, but the signature is `add_observation(message, observation_type, from_id=…)`, so `message` was the player id and `observation_type` was the raw action string. | Corrected both: `set_invalid_move(reason, reward=self._progress())` and `add_observation(message=action, observation_type=PLAYER_ACTION, from_id=…)`, then localized. | Yes — invalid-move messages now show the intended text; the action echo is now a proper PLAYER_ACTION observation. Golden reflects the corrected output. |
