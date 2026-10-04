from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Taboo-v1",
    entry_point="textarena.envs.Taboo.env:TabooEnv",
    max_rounds=4, max_attempts_per_player=6, categories=["things"],
)
