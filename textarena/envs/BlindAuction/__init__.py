from textarena.envs.registration import register

register(
    id="BlindAuction-v1",
    entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv",
    starting_capital=1000, num_items=5, conversation_rounds=3,
)
