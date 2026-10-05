from textarena.envs.registration import register

register(
    id="DontSayIt-v1",
    entry_point="textarena.envs.DontSayIt.env:DontSayItEnv",
    hardcore=False, max_turns=20,
)
register(
    id="DontSayIt-v1-hardcore",
    entry_point="textarena.envs.DontSayIt.env:DontSayItEnv",
    hardcore=True, max_turns=30,
)
