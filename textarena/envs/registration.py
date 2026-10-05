import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Union

import textarena as ta


@dataclass
class EnvSpec:
    """How to build one registered environment id."""
    id: str
    entry_point: Union[str, Callable]  # "module:Class", imported only when the environment is made
    default_wrappers: List[type]
    kwargs: Dict[str, Any] = field(default_factory=dict)


ENV_REGISTRY: Dict[str, EnvSpec] = {}


def register(id: str, entry_point: Union[str, Callable], **kwargs: Any):
    """Register a game configuration in both views:

    - `id`      -> CurrentTurnObservationWrapper (agents see only the messages since their last turn)
    - `id-mdp`  -> MDPObservationWrapper (every observation holds everything needed to act)

    Registering the same configuration again (e.g. on re-import) is a no-op; a different one under a taken id fails.
    """
    from textarena.wrappers import CurrentTurnObservationWrapper, MDPObservationWrapper
    specs = [
        EnvSpec(id=id, entry_point=entry_point, default_wrappers=[CurrentTurnObservationWrapper], kwargs=kwargs),
        EnvSpec(id=f"{id}-mdp", entry_point=entry_point, default_wrappers=[MDPObservationWrapper], kwargs=kwargs),
    ]
    for spec in specs:
        existing = ENV_REGISTRY.get(spec.id)
        if existing is not None and existing != spec:
            raise ValueError(f"Environment {spec.id} already registered with a different specification.")
    for spec in specs:
        ENV_REGISTRY.setdefault(spec.id, spec)


def make(env_id: str, **kwargs) -> ta.Env:
    """Create a registered environment, wrapped in its observation view; keyword arguments override parameters."""
    if env_id not in ENV_REGISTRY:
        current = env_id.replace("-v0", "-v1", 1)
        if "-v0" in env_id and current in ENV_REGISTRY:
            raise ValueError(f"{env_id} was retired because its rules changed; use {current} (scores are not comparable).")
        raise ValueError(f"Environment {env_id} not found in registry.")
    spec = ENV_REGISTRY[env_id]
    entry_point = spec.entry_point
    if isinstance(entry_point, str):
        module_path, class_name = entry_point.split(":")
        entry_point = getattr(importlib.import_module(module_path), class_name)
    env = entry_point(**{**spec.kwargs, **kwargs})
    env.env_id = env_id
    for wrapper in spec.default_wrappers:
        env = wrapper(env)
    return env
