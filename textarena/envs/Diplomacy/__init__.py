from textarena.envs.registration import register

register(id="Diplomacy-v1", entry_point="textarena.envs.Diplomacy.env:DiplomacyEnv", max_game_years=30)
