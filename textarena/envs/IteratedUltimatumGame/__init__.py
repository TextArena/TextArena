from textarena.envs.registration import register

register(
    id="IteratedUltimatumGame-v1",
    entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv",
    pool=50, max_turns=10, alternate_roles=False,
)
register(
    id="IteratedUltimatumGame-v1-alternate",
    entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv",
    pool=50, max_turns=12, alternate_roles=True,
)
