from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Sokoban-v1",
    entry_point="textarena.envs.Sokoban.env:SokobanEnv",
    dim_room=(6, 6), max_turns=30, num_boxes=3,
)
register_with_versions(
    id="Sokoban-v1-medium",
    entry_point="textarena.envs.Sokoban.env:SokobanEnv",
    dim_room=(8, 8), max_turns=50, num_boxes=5,
)
