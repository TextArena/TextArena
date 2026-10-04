from textarena.envs.registration import register_with_versions

register_with_versions(
    id="PublicGoodsGame-v0",
    entry_point="textarena.envs.PublicGoodsGame.env:PublicGoodsGameEnv",
    num_rounds=3, communication_turns=3, endowment=20, multiplication_factor=1.5, num_players=3,
)
