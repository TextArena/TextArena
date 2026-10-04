from textarena.envs.registration import register_with_versions

register_with_versions(
    id="PigDice-v0",
    entry_point="textarena.envs.PigDice.env:PigDiceEnv",
    winning_score=100, max_turns=100,
)
