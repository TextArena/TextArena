from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ColonelBlotto-v1",
    entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv",
    num_fields=3, num_total_units=20, num_rounds=9,
)
register_with_versions(
    id="ColonelBlotto-v1-large",
    entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv",
    num_fields=5, num_total_units=50, num_rounds=15,
)
