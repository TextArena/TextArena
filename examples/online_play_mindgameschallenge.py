import textarena as ta
 
MODEL_NAME = "Standard GPT-4o LLM"
MODEL_DESCRIPTION = "Standard OpenAI GPT-4o model."
team_hash = "MG25-XXXXXXXXXX" 


# Initialize agent
agent = ta.agents.OpenRouterAgent(model_name="google/gemma-3-27b-it:free") 

env = ta.make_mgc_online(
    track="Generalization", 
    model_name=MODEL_NAME,
    model_description=MODEL_DESCRIPTION,
    team_hash=team_hash,
    agent=agent,
    small_category=True
)
env.reset(num_players=1) # always set to 1 when playing online, even when playing multiplayer games.

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agent(observation)
    done, step_info = env.step(action=action)

rewards, game_info = env.close()