from textarena.envs.registration import register_with_versions

register_with_versions(
    id="IteratedUltimatumGame-v0",
    entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv",
    pool=50, max_turns=10, alternate_roles=False,
)
register_with_versions(
    id="IteratedUltimatumGame-v0-alternate",
    entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv",
    pool=50, max_turns=12, alternate_roles=True,
)
