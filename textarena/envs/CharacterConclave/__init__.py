from textarena.envs.registration import register_with_versions

register_with_versions(
    id="CharacterConclave-v0",
    entry_point="textarena.envs.CharacterConclave.env:CharacterConclaveEnv",
    character_budget=1000,
)
