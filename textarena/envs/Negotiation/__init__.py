from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Negotiation-v0",
    entry_point="textarena.envs.Negotiation.env:NegotiationEnv",
    turn_multiple=8,
)
