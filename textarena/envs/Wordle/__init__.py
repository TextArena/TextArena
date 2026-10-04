from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Wordle-v0",
    entry_point="textarena.envs.Wordle.env:WordleEnv",
    hardcore=False, word_length=5, num_guesses=6,
)
register_with_versions(
    id="Wordle-v0-hardcore",
    entry_point="textarena.envs.Wordle.env:WordleEnv",
    hardcore=True, word_length=5, num_guesses=6,
)
