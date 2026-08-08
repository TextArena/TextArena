import textarena as ta

env_id = 'UltimateTicTacToe-v0'
predefined_actions = [
    '[8 2]',
    '[2 8]',
    '[8 1]',
    '[1 4]',
    '[4 4]',
    '[4 7]',
    '[7 2]',
    '[2 2]',
    '[2 4]',
    '[4 1]',
    '[1 5]',
    '[5 3]',
    '[3 7]',
    '[7 1]',
    '[1 0]',
    '[0 7]',
    '[7 7]',
    '[7 4]',
    '[4 6]',
    '[6 2]',
    '[2 5]',
    '[5 2]',
    '[2 6]',
    '[6 7]',
    '[7 5]',
    '[5 8]',
    '[8 6]',
    '[6 3]',
    '[3 3]',
    '[3 1]',
    '[1 6]',
    '[6 0]',
    '[0 3]',
    '[3 4]',
    '[4 5]',
    '[5 7]',
    '[7 8]',
    '[8 7]',
    '[8 4]',
    '[4 3]',
    '[3 8]',
    '[3 6]',
    '[6 8]',
    '[6 1]',
    '[1 1]',
    '[1 3]',
    '[3 2]',
    '[2 3]',
    '[3 5]',
    '[5 0]',
    '[0 0]',
    '[0 4]',
    '[4 0]',
    '[0 6]',
    '[0 8]',
    '[0 5]',
    '[5 1]',
    '[1 7]',
    '[1 8]',
    '[1 2]',
    '[2 7]',
    '[2 1]',
    '[2 0]',
    '[0 1]',
    '[4 8]',
    '[5 4]',
]


env = ta.make(env_id=env_id)
env.reset(num_players=2)

for istep, action in enumerate(predefined_actions):
    done, _ = env.step(action=action)
    if istep == len(predefined_actions) - 1:
        assert done, 'Game must end after the last move.'
    else:
        assert not done, 'Game must not yet end before the last move.'

print(f'{env_id=} test done successfully.')
