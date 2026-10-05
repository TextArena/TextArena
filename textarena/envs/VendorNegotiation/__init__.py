from textarena.envs.registration import register

register(
    id="VendorNegotiation-v1",
    entry_point="textarena.envs.VendorNegotiation.env:VendorNegotiationEnv",
    num_products=5, max_rounds=20,
)
