from textarena.envs.registration import register

register(
    id="SimpleNegotiation-v1",
    entry_point="textarena.envs.SimpleNegotiation.env:SimpleNegotiationEnv",
    max_turns=10,
)
