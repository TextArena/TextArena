from textarena.envs.registration import register

register(
    id="Mastermind-v1",
    entry_point="textarena.envs.Mastermind.env:MastermindEnv",
    code_length=4, num_numbers=6, max_turns=20, duplicate_numbers=False,
)
register(
    id="Mastermind-v1-hard",
    entry_point="textarena.envs.Mastermind.env:MastermindEnv",
    code_length=4, num_numbers=8, max_turns=30, duplicate_numbers=False,
)
