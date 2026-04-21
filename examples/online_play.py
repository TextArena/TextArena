import textarena as ta
MODEL_NAME = "Llama 3.3 70B LLM"
MODEL_DESCRIPTION = "Groq Llama 3.3 70B Versatile model."
EMAIL = "your.email@example.com"

# Initialize agent
agent = ta.agents.OpenRouterAgent(model_name="google/gemma-3-27b-it:free") 

env = ta.make_online(
    env_id=["SpellingBee-v0", "SimpleNegotiation-v0", "Poker-v0"], 
    model_name=MODEL_NAME,
    model_description=MODEL_DESCRIPTION,
    email=EMAIL,
    agent=agent
)
env.reset(num_players=1) # always set to 1 when playing online, even when playing multiplayer games.

done = False
while not done:
    player_id, observation = env.get_observation()
    action = agent(observation)
    done, step_info = env.step(action=action)

rewards, game_info = env.close()