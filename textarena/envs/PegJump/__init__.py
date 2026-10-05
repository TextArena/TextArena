from textarena.envs.registration import register

register(id="PegJump-v1", entry_point="textarena.envs.PegJump.env:PegJumpEnv", initial_empty=5)
