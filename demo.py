"""A minimal script showing how to run TextArena locally."""

import textarena as ta

agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.HumanAgent(),
}

# Initialize the environment
env = ta.make(env_id="TicTacToe-v1")

# Optionally, show each player the game in their own language
# env = ta.wrappers.TranslationWrapper(env, lang={0: "en", 1: "de"})

env.reset(num_players=len(agents))

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done = env.step(action)

rewards, game_info = env.close()

print(rewards)
print(game_info)
