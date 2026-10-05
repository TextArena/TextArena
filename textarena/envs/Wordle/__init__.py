from textarena.envs.registration import register

register(
    id="Wordle-v1",
    entry_point="textarena.envs.Wordle.env:WordleEnv",
    hardcore=False, word_length=5, num_guesses=6,
)
register(
    id="Wordle-v1-hardcore",
    entry_point="textarena.envs.Wordle.env:WordleEnv",
    hardcore=True, word_length=5, num_guesses=6,
)
