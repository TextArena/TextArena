import re, random, importlib
from typing import Any, Union, List, Callable, Dict, Tuple, Optional
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
    
def register(id: str, entry_point: Callable, default_wrappers: Optional[List[ta.Wrapper]]=None, **kwargs: Any):
    """Register an environment with a given ID."""
    if id in ENV_REGISTRY:
        raise ValueError(f"Environment {id} already registered.")
    ENV_REGISTRY[id] = EnvSpec(id=id, entry_point=entry_point, default_wrappers=default_wrappers, kwargs=kwargs)

def register_with_versions(id: str, entry_point: Callable, wrappers: Optional[Dict[str, List[ta.Wrapper]]]=None, **kwargs: Any):
    """Register an environment with a given ID."""
    if id in ENV_REGISTRY: raise ValueError(f"Environment {id} already registered.")

    # first register default version
    ENV_REGISTRY[id] = EnvSpec(id=id, entry_point=entry_point, default_wrappers=wrappers.get("default"), kwargs=kwargs)
    for wrapper_version_key in list(wrappers.keys())+["-raw"]:
        if wrapper_version_key=="default": continue
        ENV_REGISTRY[f"{id}{wrapper_version_key}"] = EnvSpec(id=f"{id}{wrapper_version_key}", entry_point=entry_point, default_wrappers=wrappers.get(wrapper_version_key), kwargs=kwargs)

def pprint_registry_detailed():
    """Pretty print the registry with additional details like kwargs."""
    if not ENV_REGISTRY:
        print("No environments registered.")
    else:
        print("Detailed Registered Environments:")
        for env_id, env_spec in ENV_REGISTRY.items():
            print(f"  - {env_id}:")
            print(f"      Entry Point: {env_spec.entry_point}")
            print(f"      Kwargs:      {env_spec.kwargs}")
            print(f"      Wrappers:    {env_spec.default_wrappers}")

def check_env_exists(env_id: str):
    """Check if an environment exists in the registry."""
    if env_id not in ENV_REGISTRY:
        raise ValueError(f"Environment {env_id} is not registered.")
    else:
        print(f"Environment {env_id} is registered.")

def make(env_id: Union[str, List[str]], lang: str = "en", **kwargs) -> Any:
    """
    Create an environment instance using the registered ID.
    
    Args:
        env_id: Registered environment ID, or a list to pick from randomly.
        lang:   ISO 639-1 language code for the environment's locale (default: 'en').
        **kwargs: Additional keyword arguments passed to the environment constructor.
    """
    # If env_id is a list, randomly select one environment ID
    if isinstance(env_id, list):
        if not env_id:
            raise ValueError("Empty list of environment IDs provided.")
        env_id = random.choice(env_id)
    
    if env_id not in ENV_REGISTRY:
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
    
    env = env_class(**{**env_spec.kwargs, **kwargs}, lang=lang)

    # Dynamically attach the env_id
    env.env_id = env_id
    env.entry_point = env_spec.entry_point

    # wrap the environment
    if env_spec.default_wrappers is not None and len(env_spec.default_wrappers) > 0:
        for wrapper in env_spec.default_wrappers:
            env = wrapper(env)

    return env