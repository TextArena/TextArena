from textarena.envs.registration import register

register(
    id="CharacterConclave-v1",
    entry_point="textarena.envs.CharacterConclave.env:CharacterConclaveEnv",
    character_budget=1000,
)
