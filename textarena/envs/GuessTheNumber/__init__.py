from textarena.envs.registration import register_with_versions

register_with_versions(
    id="GuessTheNumber-v0",
    entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv",
    min_number=1, max_number=20, max_turns=10,
)
register_with_versions(
    id="GuessTheNumber-v0-hardcore",
    entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv",
    min_number=1, max_number=50, max_turns=10,
)
