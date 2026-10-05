from textarena.envs.registration import register

register(
    id="Negotiation-v1",
    entry_point="textarena.envs.Negotiation.env:NegotiationEnv",
    turn_multiple=8,
)
