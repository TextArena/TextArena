from textarena.envs.registration import register_with_versions

register_with_versions(
    id="BlindAuction-v0",
    entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv",
    starting_capital=1000, num_items=5, conversation_rounds=3,
)
