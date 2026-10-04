""" A minimal script showing how to run textarena locally """

import textarena as ta


agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.OpenRouterAgent(model_name="moonshotai/kimi-k2:free"),
}

# initialize the environment
# env = ta.make(env_id="TicTacToe-v1-mdp")
env = ta.make(env_id="Chess-v1")
env.reset(num_players=len(agents))

# main game loop
done = False
while not done:
  player_id, observation = env.get_observation()
  action = agents[player_id](observation)
  done = env.step(action=action)
rewards, game_info = env.close()

print(f"Rewards: {rewards}")
print(f"Game Info: {game_info}")
