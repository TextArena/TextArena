"""A minimal script showing how to run TextArena locally."""

import textarena as ta

agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.HumanAgent()
}

# Initialize the environment
env = ta.make(env_id="TicTacToe-v0-train")

# Reset the environment with the number of players
env.reset(num_players=len(agents))

# Alternatively, assign a language to each player
# env.reset(
#     num_players=len(agents),
#     lang_mapping={0: "en", 1: "de"}
# )

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action)

rewards, game_info = env.close()

print(rewards)
print(game_info)