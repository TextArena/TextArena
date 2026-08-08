""" A minimal script showing how to run textarena locally """

import textarena as ta 
import os 

agents = {
    0: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),
    1: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),
    2: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),
    3: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),# 
    4: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),
    # 5: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',region_name='us-west-2'),
}

# agents = {
#     0: ta.agents.HumanAgent(),
#     1: ta.agents.HumanAgent(),
#     2: ta.agents.HumanAgent(),
#     3: ta.agents.HumanAgent(), 
#     4: ta.agents.HumanAgent(),
#     # 5: ta.agents.HumanAgent(),
# }


# initialize the environment
env = ta.make(env_id="NegotiateToSurvive-v0-distributive")
env.reset(num_players=len(agents))

# main game loop
done = False 
while not done:
  player_id, observation = env.get_observation()
  print(player_id, observation)
  action = agents[player_id](observation) 
  done, step_info = env.step(action=action)
rewards, game_info = env.close()

print(f"Rewards: {rewards}")
print(f"Game Info: {game_info}")