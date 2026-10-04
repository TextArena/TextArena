from textarena.envs.registration import register

register(
    id="ColonelBlotto-v1",
    entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv",
    num_fields=3, num_total_units=20, num_rounds=9,
)
register(
    id="ColonelBlotto-v1-large",
    entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv",
    num_fields=5, num_total_units=50, num_rounds=15,
)
