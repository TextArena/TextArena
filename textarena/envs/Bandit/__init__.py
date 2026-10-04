from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Bandit-v1",
    entry_point="textarena.envs.Bandit.env:BanditEnv",
    buttons=["red", "blue", "green", "yellow", "purple"], p_gap=0.1, num_turns=20,
)
register_with_versions(
    id="Bandit-v1-hard",
    entry_point="textarena.envs.Bandit.env:BanditEnv",
    buttons=["red", "blue", "green", "yellow", "purple", "orange", "pink", "brown", "gray", "black"],
    p_gap=0.05,
    num_turns=40,
)
