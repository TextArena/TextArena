from textarena.envs.registration import register_with_versions

register_with_versions(
    id="LetterAuction-v0",
    entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv",
    starting_coins=100,
)
register_with_versions(
    id="LetterAuction-v0-hard",
    entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv",
    starting_coins=25,
)
