from textarena.envs.registration import register_with_versions

register_with_versions(id="Diplomacy-v1", entry_point="textarena.envs.Diplomacy.env:DiplomacyEnv", max_game_years=30)
