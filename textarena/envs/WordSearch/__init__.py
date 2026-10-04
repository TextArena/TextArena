from textarena.envs.registration import register

register(id="WordSearch-v1", entry_point="textarena.envs.WordSearch.env:WordSearchEnv", hardcore=False)
register(
    id="WordSearch-v1-hardcore",
    entry_point="textarena.envs.WordSearch.env:WordSearchEnv",
    hardcore=True,
)
