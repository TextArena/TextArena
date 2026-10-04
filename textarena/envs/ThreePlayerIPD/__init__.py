from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ThreePlayerIPD-v0",
    entry_point="textarena.envs.ThreePlayerIPD.env:ThreePlayerIPDEnv",
    num_rounds=5, communication_turns=1, cooperate_reward=3, defect_reward=5, sucker_reward=0, mutual_defect_reward=1,
)
