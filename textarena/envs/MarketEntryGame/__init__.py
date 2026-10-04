from textarena.envs.registration import register_with_versions

register_with_versions(
    id="MarketEntryGame-v1",
    entry_point="textarena.envs.MarketEntryGame.env:MarketEntryGameEnv",
    num_rounds=5,
    communication_turns=3,
    market_capacity=2,
    entry_profit=15,
    overcrowding_penalty=-5,
    safe_payoff=5,
    default_num_players=4,
)
