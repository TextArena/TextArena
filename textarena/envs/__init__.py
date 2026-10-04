"""Every game folder registers its own environment ids in its ``__init__.py``."""
import importlib
import pkgutil

for _game in pkgutil.iter_modules(__path__):
    if _game.ispkg:
        importlib.import_module(f"{__name__}.{_game.name}")
