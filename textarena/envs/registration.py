import random, importlib
from typing import Any, Union, List, Callable, Dict, Optional
from dataclasses import dataclass, field

import textarena as ta 


# Global environment registry
ENV_REGISTRY: Dict[str, Callable] = {}

@dataclass
class EnvSpec:
    """A specification for creating environments."""
    id: str
    entry_point: Callable
    default_wrappers: Optional[List[ta.Wrapper]]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def make(self, **kwargs) -> Any:
        """Create an environment instance."""
        all_kwargs = {**self.kwargs, **kwargs}
        return self.entry_point(**all_kwargs)


def _register_specs(specs: List[EnvSpec]):
    """Register equivalent re-imports idempotently, but reject real conflicts."""
    for spec in specs:
        existing = ENV_REGISTRY.get(spec.id)
        if existing is not None and existing != spec:
            raise ValueError(f"Environment {spec.id} already registered with a different specification.")
    for spec in specs:
        ENV_REGISTRY.setdefault(spec.id, spec)


def register(id: str, entry_point: Callable, default_wrappers: Optional[List[ta.Wrapper]]=None, **kwargs: Any):
    """Register an environment with a given ID."""
    _register_specs([
        EnvSpec(id=id, entry_point=entry_point, default_wrappers=default_wrappers, kwargs=kwargs)
    ])

def register_with_versions(id: str, entry_point: Callable, **kwargs: Any):
    """Register both views of an environment configuration:

    - `id`      -> CurrentTurnObservationWrapper (agents see only the messages since their last turn)
    - `id-mdp`  -> MDPObservationWrapper (every observation holds everything needed to act)
    """
    from textarena.wrappers import CurrentTurnObservationWrapper, MDPObservationWrapper
    _register_specs([
        EnvSpec(id=id, entry_point=entry_point, default_wrappers=[CurrentTurnObservationWrapper], kwargs=kwargs),
        EnvSpec(id=f"{id}-mdp", entry_point=entry_point, default_wrappers=[MDPObservationWrapper], kwargs=kwargs),
    ])

def make(env_id: Union[str, List[str]], **kwargs) -> Any:
    """Create an environment instance using the registered ID."""
    # If env_id is a list, randomly select one environment ID
    if isinstance(env_id, list):
        if not env_id:
            raise ValueError("Empty list of environment IDs provided.")
        env_id = random.choice(env_id)
    
    if env_id not in ENV_REGISTRY:
        current = env_id.replace("-v0", "-v1", 1)
        if "-v0" in env_id and current in ENV_REGISTRY:
            raise ValueError(f"{env_id} was retired because its rules changed; use {current} (scores are not comparable).")
        raise ValueError(f"Environment {env_id} not found in registry.")

    env_spec = ENV_REGISTRY[env_id]
    
    # Resolve the entry point if it's a string
    if isinstance(env_spec.entry_point, str):
        module_path, class_name = env_spec.entry_point.split(":")
        try:
            module = importlib.import_module(module_path)
            env_class = getattr(module, class_name)
        except (ModuleNotFoundError, AttributeError) as e:
            raise ImportError(f"Could not import {module_path}.{class_name}. Error: {e}")
    else:
        env_class = env_spec.entry_point
    
    env = env_class(**{**env_spec.kwargs, **kwargs})

    # Dynamically attach the env_id
    env.env_id = env_id
    env.entry_point = env_spec.entry_point

    # wrap the environment
    if env_spec.default_wrappers is not None and len(env_spec.default_wrappers) > 0:
        for wrapper in env_spec.default_wrappers:
            env = wrapper(env)

    return env
