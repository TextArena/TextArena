""" A minimal script showing how to run textarena locally """

import textarena as ta 

agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.HumanAgent(),
}

# initialize the environment
env = ta.make(env_id="TicTacToe-v0-train")
env.reset(num_players=len(agents), lang_mapping={0: "zh", 1: "en"}) # You can also just pass a single lang string if all players will use the same one, e.g. lang="en"

# main game loop
done = False 
while not done:
  player_id, observation = env.get_observation()
  action = agents[player_id](observation)
  done, step_info = env.step(action=action)
rewards, game_info = env.close()
print(rewards)
print(game_info)
