from textarena.envs.registration import register

register(id="Debate-v1", entry_point="textarena.envs.Debate.env:DebateEnv", max_turns=6, jury_size=7)
