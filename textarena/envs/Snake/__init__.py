from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Snake-v0",
    entry_point="textarena.envs.Snake.env:SnakeEnv",
    width=5, height=5, num_apples=2, max_turns=40,
)
