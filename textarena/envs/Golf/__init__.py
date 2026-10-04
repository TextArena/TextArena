from textarena.envs.registration import register_with_versions

register_with_versions(id="Golf-v1", entry_point="textarena.envs.Golf.env:GolfEnv", num_cards=6, num_columns=3)
register_with_versions(id="Golf-v1-medium", entry_point="textarena.envs.Golf.env:GolfEnv", num_cards=9, num_columns=3)
