from textarena.envs.registration import register_with_versions

register_with_versions(id="LiarsDice-v1", entry_point="textarena.envs.LiarsDice.env:LiarsDiceEnv", num_dice=5)
