from textarena.envs.registration import register_with_versions

register_with_versions(id="Secretary-v0", entry_point="textarena.envs.Secretary.env:SecretaryEnv", N=5)
