from textarena.envs.registration import register_with_versions

register_with_versions(id="TwoDollar-v1", entry_point="textarena.envs.TwoDollar.env:TwoDollarEnv")
