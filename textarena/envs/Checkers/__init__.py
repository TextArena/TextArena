from textarena.envs.registration import register

register(id="Checkers-v1", entry_point="textarena.envs.Checkers.env:CheckersEnv", max_turns=100)
