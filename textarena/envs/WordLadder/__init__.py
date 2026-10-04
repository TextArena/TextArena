from textarena.envs.registration import register_with_versions

register_with_versions(
    id="WordLadder-v1",
    entry_point="textarena.envs.WordLadder.env:WordLadderEnv",
    min_distance=5, max_distance=7, max_turns=100,
)
register_with_versions(
    id="WordLadder-v1-hard",
    entry_point="textarena.envs.WordLadder.env:WordLadderEnv",
    min_distance=13, max_distance=15, max_turns=100,
)
