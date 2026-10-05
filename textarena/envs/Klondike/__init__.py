from textarena.envs.registration import register

register(
    id="Klondike-v1",
    entry_point="textarena.envs.Klondike.env:KlondikeEnv",
    max_turns=200, draw_count=1,
)
