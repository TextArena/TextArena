from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Poker-v1",
    entry_point="textarena.envs.Poker.env:PokerEnv",
    num_rounds=10, starting_chips=1000, small_blind=10, big_blind=20,
)
