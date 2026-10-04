from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Bohnanza-v1",
    entry_point="textarena.envs.Bohnanza.env:BohnanzaEnv",
    deck_cycles=3, max_trade_rounds=None, max_turns=3000,
)
register_with_versions(
    id="Bohnanza-v1-short",
    entry_point="textarena.envs.Bohnanza.env:BohnanzaEnv",
    deck_cycles=1, max_trade_rounds=3, max_turns=1000,
)
