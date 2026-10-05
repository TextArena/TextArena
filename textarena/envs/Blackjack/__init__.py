from textarena.envs.registration import register

register(id="Blackjack-v1", entry_point="textarena.envs.Blackjack.env:BlackjackEnv", num_hands=5)
