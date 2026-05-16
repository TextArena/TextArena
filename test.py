""" A minimal script showing how to run textarena locally """

import textarena as ta 

agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.HumanAgent(),
}

# initialize the environment
env = ta.make(env_id="TicTacToe-v0", lang={0: "en", 1: "zh"})
env.reset(num_players=len(agents))

# main game loop
done = False 
while not done:
  player_id, observation = env.get_observation()
  action = agents[player_id](observation)
  done, step_info = env.step(action=action)
rewards, game_info = env.close()
print(rewards)
print(game_info)
