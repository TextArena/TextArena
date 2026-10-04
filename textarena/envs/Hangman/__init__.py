from textarena.envs.registration import register

register(id="Hangman-v1", entry_point="textarena.envs.Hangman.env:HangmanEnv", hardcore=False)
register(id="Hangman-v1-hardcore", entry_point="textarena.envs.Hangman.env:HangmanEnv", hardcore=True)
