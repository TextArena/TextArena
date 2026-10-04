from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Klondike-v0",
    entry_point="textarena.envs.Klondike.env:KlondikeEnv",
    max_turns=200, draw_count=1,
)
