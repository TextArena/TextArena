from textarena.envs.registration import register

register(
    id="LetterAuction-v1",
    entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv",
    starting_coins=100,
)
register(
    id="LetterAuction-v1-hard",
    entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv",
    starting_coins=25,
)
