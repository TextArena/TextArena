from textarena.envs.registration import register_with_versions

register_with_versions(id="WordSearch-v1", entry_point="textarena.envs.WordSearch.env:WordSearchEnv", hardcore=False)
register_with_versions(
    id="WordSearch-v1-hardcore",
    entry_point="textarena.envs.WordSearch.env:WordSearchEnv",
    hardcore=True,
)
