from textarena.envs.registration import register_with_versions

register_with_versions(
    id="SimpleBlindAuction-v1",
    entry_point="textarena.envs.SimpleBlindAuction.env:SimpleBlindAuctionEnv",
    starting_capital=1000, num_items=5, conversation_rounds=3,
)
