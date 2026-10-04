from textarena.envs.registration import register

register(id="Codenames-v1", entry_point="textarena.envs.Codenames.env:CodenamesEnv", hardcore=False)
register(
    id="Codenames-v1-hardcore",
    entry_point="textarena.envs.Codenames.env:CodenamesEnv",
    hardcore=True,
)
