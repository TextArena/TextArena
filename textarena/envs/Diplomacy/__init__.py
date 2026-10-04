from textarena.envs.registration import register_with_versions

register_with_versions(id="Diplomacy-v0", entry_point="textarena.envs.Diplomacy.env:DiplomacyEnv", max_turns=30)
