from textarena.envs.registration import register_with_versions

register_with_versions(
    id="UsedCarNegotiation-v1",
    entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv",
    max_rounds=10,
)
