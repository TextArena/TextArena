from textarena.envs.registration import register_with_versions

register_with_versions(
    id="TwentyQuestions-v1",
    entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv",
    hardcore=False,
)
register_with_versions(
    id="TwentyQuestions-v1-hardcore",
    entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv",
    hardcore=True,
)
