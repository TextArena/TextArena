""" A minimal script showing how to run textarena locally """

import textarena as ta 

agents = {
    0: ta.agents.HumanAgent(),
    1: ta.agents.HumanAgent(),
}

# initialize the environment
env = ta.make(env_id="TicTacToe-v0")
# for multilingual environments (TicTacToe, ColonelBlotto, KuhnPoker, IteratedPrisonersDilemma,
# PigDice, Nim, SimpleNegotiation, ConnectFour), you can specify the language for each player. 
# For example, if player 0 speaks English and player 1 speaks Chinese, you can do:
# Available languages - en, zh, fr, de, es, ms, he, ar
# env = ta.make(env_id="TicTacToe-v0", lang={0: "en", 1: "zh"})
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
