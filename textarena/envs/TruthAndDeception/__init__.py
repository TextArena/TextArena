from textarena.envs.registration import register_with_versions

register_with_versions(
    id="TruthAndDeception-v1",
    entry_point="textarena.envs.TruthAndDeception.env:TruthAndDeceptionEnv",
    max_turns=6,
)
