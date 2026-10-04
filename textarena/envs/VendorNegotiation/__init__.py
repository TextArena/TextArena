from textarena.envs.registration import register_with_versions

register_with_versions(
    id="VendorNegotiation-v0",
    entry_point="textarena.envs.VendorNegotiation.env:VendorNegotiationEnv",
    num_products=5, max_rounds=20,
)
