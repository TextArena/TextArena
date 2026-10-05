from textarena.envs.registration import register

register(
    id="IteratedMatchingPennies-v1",
    entry_point="textarena.envs.IteratedMatchingPennies.env:IteratedMatchingPenniesEnv",
    num_rounds=10,
)
