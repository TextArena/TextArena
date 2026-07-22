"""Reusable golden-transcript runner for multilingual env verification.

Drives a raw env through fixed action scripts and serializes every observation
(plus rewards / game_info) into a canonical, diffable structure. Used to prove a
localization refactor is behaviour-preserving: capture the golden from the
ORIGINAL env, then assert the refactored env reproduces it byte-for-byte in
English.

No third-party deps; runs under plain `python3`.
"""
import importlib
import json


def load_env(entry):
    """entry = 'package.module:ClassName' -> the class object."""
    mod_path, cls_name = entry.split(":")
    module = importlib.import_module(mod_path)
    return getattr(module, cls_name)


def run_scenario(EnvCls, actions, lang_mapping, num_players=2, seed=42):
    env = EnvCls()
    env.reset(num_players=num_players, seed=seed, lang_mapping=lang_mapping)
    log = []
    for act in actions:
        pid, obs = env.get_observation()
        for (from_id, text, otype) in obs:
            log.append({"to": pid, "from": from_id, "type": otype.name, "text": text})
        done, info = env.step(action=act)
        log.append({"action": act, "done": done, "info": info})
        if done:
            break
    # Capture observations produced by the final action (e.g. an invalid-move
    # admin message on the last turn), which the loop above would otherwise miss.
    pid, obs = env.get_observation()
    for (from_id, text, otype) in obs:
        log.append({"trailing_to": pid, "from": from_id, "type": otype.name, "text": text})
    rewards, game_info = env.close()
    return {"observations": log, "rewards": rewards, "game_info": game_info}


def run_game(spec, lang):
    """Run every scenario in a game spec at a single language.

    spec = {"entry": "...:Cls", "scenarios": {name: [actions]}, "num_players": 2, "seed": 42}
    """
    EnvCls = load_env(spec["entry"])
    n = spec.get("num_players", 2)
    seed = spec.get("seed", 42)
    lang_mapping = {i: lang for i in range(n)}
    return {
        name: run_scenario(EnvCls, actions, dict(lang_mapping), num_players=n, seed=seed)
        for name, actions in spec["scenarios"].items()
    }


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
