from textarena.envs.registration import register

register(
    id="Surround-v1",
    entry_point="textarena.envs.Surround.env:SurroundEnv",
    width=5, height=5, max_turns=40,
)
