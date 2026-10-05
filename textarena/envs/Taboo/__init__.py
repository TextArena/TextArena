from textarena.envs.registration import register

register(
    id="Taboo-v1",
    entry_point="textarena.envs.Taboo.env:TabooEnv",
    max_rounds=4, max_attempts_per_player=6, categories=["things"],
)
