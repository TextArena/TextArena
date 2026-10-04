from textarena.envs.registration import register_with_versions

register_with_versions(id="Hangman-v1", entry_point="textarena.envs.Hangman.env:HangmanEnv", hardcore=False)
register_with_versions(id="Hangman-v1-hardcore", entry_point="textarena.envs.Hangman.env:HangmanEnv", hardcore=True)
