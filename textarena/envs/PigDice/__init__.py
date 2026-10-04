from textarena.envs.registration import register

register(
    id="PigDice-v1",
    entry_point="textarena.envs.PigDice.env:PigDiceEnv",
    winning_score=100, max_turns=100,
)
