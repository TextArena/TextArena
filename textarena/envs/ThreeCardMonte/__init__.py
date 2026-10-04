from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ThreeCardMonte-v0",
    entry_point="textarena.envs.ThreeCardMonte.env:ThreeCardMonteEnv",
    num_cups=3, steps=10,
)
