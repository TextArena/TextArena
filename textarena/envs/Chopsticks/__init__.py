from textarena.envs.registration import register

register(id="Chopsticks-v1", entry_point="textarena.envs.Chopsticks.env:ChopsticksEnv", max_turns=40)
