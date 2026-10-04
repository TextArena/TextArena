from textarena.envs.registration import register

register(
    id="UsedCarNegotiation-v1",
    entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv",
    max_rounds=10,
)
