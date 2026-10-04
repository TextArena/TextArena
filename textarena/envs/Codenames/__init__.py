from textarena.envs.registration import register_with_versions

register_with_versions(id="Codenames-v0", entry_point="textarena.envs.Codenames.env:CodenamesEnv", hardcore=False)
register_with_versions(
    id="Codenames-v0-hardcore",
    entry_point="textarena.envs.Codenames.env:CodenamesEnv",
    hardcore=True,
)
