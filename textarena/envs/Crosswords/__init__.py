from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Crosswords-v0",
    entry_point="textarena.envs.Crosswords.env:CrosswordsEnv",
    hardcore=False, max_turns=30, num_words=3,
)
register_with_versions(
    id="Crosswords-v0-hardcore",
    entry_point="textarena.envs.Crosswords.env:CrosswordsEnv",
    hardcore=True, max_turns=30, num_words=3,
)
