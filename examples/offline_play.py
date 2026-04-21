""" A minimal script showing how to run textarena locally """

import textarena as ta 


agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.OpenRouterAgent(model_name="google/gemma-3-27b-it:free"), 
}

# initialize the environment
#env = ta.make(env_id="TicTacToe-v0-train")
env = ta.make(env_id="Chess-v0") 
env.reset(num_players=len(agents))

# main game loop
done = False 
while not done:
  player_id, observation = env.get_observation()
  action = agents[player_id](observation)
  done, step_info = env.step(action=action)
rewards, game_info = env.close()

print(f"Rewards: {rewards}")
print(f"Game Info: {game_info}")