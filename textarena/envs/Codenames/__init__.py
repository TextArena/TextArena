from textarena.envs.registration import register_with_versions

register_with_versions(id="Codenames-v1", entry_point="textarena.envs.Codenames.env:CodenamesEnv", hardcore=False)
register_with_versions(
    id="Codenames-v1-hardcore",
    entry_point="textarena.envs.Codenames.env:CodenamesEnv",
    hardcore=True,
)
