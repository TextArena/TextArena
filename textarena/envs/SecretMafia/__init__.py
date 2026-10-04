from textarena.envs.registration import register_with_versions

register_with_versions(
    id="SecretMafia-v1",
    entry_point="textarena.envs.SecretMafia.env:SecretMafiaEnv",
    mafia_ratio=0.25, discussion_rounds=3,
)
