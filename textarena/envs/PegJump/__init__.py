from textarena.envs.registration import register_with_versions

register_with_versions(id="PegJump-v1", entry_point="textarena.envs.PegJump.env:PegJumpEnv", initial_empty=5)
