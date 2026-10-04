from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Mastermind-v1",
    entry_point="textarena.envs.Mastermind.env:MastermindEnv",
    code_length=4, num_numbers=6, max_turns=20, duplicate_numbers=False,
)
register_with_versions(
    id="Mastermind-v1-hard",
    entry_point="textarena.envs.Mastermind.env:MastermindEnv",
    code_length=4, num_numbers=8, max_turns=30, duplicate_numbers=False,
)
