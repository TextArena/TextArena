from textarena.envs.registration import register_with_versions

register_with_versions(
    id="GuessTheNumber-v1",
    entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv",
    min_number=1, max_number=20, max_turns=10,
)
register_with_versions(
    id="GuessTheNumber-v1-hardcore",
    entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv",
    min_number=1, max_number=50, max_turns=10,
)
