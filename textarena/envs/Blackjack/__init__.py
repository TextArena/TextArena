from textarena.envs.registration import register_with_versions

register_with_versions(id="Blackjack-v0", entry_point="textarena.envs.Blackjack.env:BlackjackEnv", num_hands=5)
