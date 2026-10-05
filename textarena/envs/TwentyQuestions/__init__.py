from textarena.envs.registration import register

register(
    id="TwentyQuestions-v1",
    entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv",
    hardcore=False,
)
register(
    id="TwentyQuestions-v1-hardcore",
    entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv",
    hardcore=True,
)
