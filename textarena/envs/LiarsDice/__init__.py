from textarena.envs.registration import register

register(id="LiarsDice-v1", entry_point="textarena.envs.LiarsDice.env:LiarsDiceEnv", num_dice=5)
