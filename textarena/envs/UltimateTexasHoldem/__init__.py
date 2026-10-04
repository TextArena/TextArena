from textarena.envs.registration import register_with_versions

register_with_versions(
    id="UltimateTexasHoldem-v0",
    entry_point="textarena.envs.UltimateTexasHoldem.env:UltimateTexasHoldemEnv",
    max_turns=1000, start_chips=1000, ante_amount=25,
)
