from textarena.envs.registration import register

register(id="Secretary-v1", entry_point="textarena.envs.Secretary.env:SecretaryEnv", N=5)
