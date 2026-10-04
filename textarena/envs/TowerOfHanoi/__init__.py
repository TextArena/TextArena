from textarena.envs.registration import register_with_versions

register_with_versions(
    id="TowerOfHanoi-v0",
    entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv",
    num_disks=3, max_turns=14,
)
register_with_versions(
    id="TowerOfHanoi-v0-hard",
    entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv",
    num_disks=5, max_turns=62,
)
