from textarena.envs.registration import register_with_versions

register_with_versions(
    id="SimpleNegotiation-v0",
    entry_point="textarena.envs.SimpleNegotiation.env:SimpleNegotiationEnv",
    max_turns=10,
)
