from textarena.envs.registration import register

register(
    id="Crosswords-v1",
    entry_point="textarena.envs.Crosswords.env:CrosswordsEnv",
    hardcore=False, max_turns=30, num_words=3,
)
register(
    id="Crosswords-v1-hardcore",
    entry_point="textarena.envs.Crosswords.env:CrosswordsEnv",
    hardcore=True, max_turns=30, num_words=3,
)
