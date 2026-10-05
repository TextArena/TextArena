from textarena.envs.registration import register

register(
    id="IteratedStagHunt-v1",
    entry_point="textarena.envs.IteratedStagHunt.env:IteratedStagHuntEnv",
    num_rounds=5,
    conversation_rounds=3,
    mutual_stag_reward=10,
    single_hare_reward=8,
    single_stag_reward=1,
    mutual_hare_reward=5,
    randomize_payoff=False,
)
register(
    id="IteratedStagHunt-v1-randomized",
    entry_point="textarena.envs.IteratedStagHunt.env:IteratedStagHuntEnv",
    num_rounds=5,
    conversation_rounds=3,
    mutual_stag_reward=10,
    single_hare_reward=8,
    single_stag_reward=1,
    mutual_hare_reward=5,
    randomize_payoff=True,
)
