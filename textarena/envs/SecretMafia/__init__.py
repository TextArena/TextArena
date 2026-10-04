from textarena.envs.registration import register

register(
    id="SecretMafia-v1",
    entry_point="textarena.envs.SecretMafia.env:SecretMafiaEnv",
    mafia_ratio=0.25, discussion_rounds=3,
)
