from textarena.envs.registration import register

register(
    id="TruthAndDeception-v1",
    entry_point="textarena.envs.TruthAndDeception.env:TruthAndDeceptionEnv",
    max_turns=6,
)
