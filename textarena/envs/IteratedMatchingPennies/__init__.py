from textarena.envs.registration import register_with_versions

register_with_versions(
    id="IteratedMatchingPennies-v1",
    entry_point="textarena.envs.IteratedMatchingPennies.env:IteratedMatchingPenniesEnv",
    num_rounds=10,
)
