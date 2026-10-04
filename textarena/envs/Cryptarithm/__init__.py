from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Cryptarithm-v1",
    entry_point="textarena.envs.Cryptarithm.env:CryptarithmEnv",
    equation="SEND + MORE = MONEY", max_turns=100,
)
