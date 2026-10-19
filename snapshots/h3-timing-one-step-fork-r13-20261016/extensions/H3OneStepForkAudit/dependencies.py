"""Resolve frozen sibling helpers under Comfy's path-based node loader."""
import hashlib
import importlib
from pathlib import Path
import sys
import types

_ROOT = Path(__file__).resolve().parent.parent
_NAME = '_h3_fork_dependencies_' + hashlib.sha256(str(_ROOT).encode()).hexdigest()[:16]
if _NAME not in sys.modules:
    package = types.ModuleType(_NAME)
    package.__path__ = [str(_ROOT)]
    sys.modules[_NAME] = package

counterfactual = importlib.import_module(_NAME + '.H3CounterfactualRouter.core')
guards = importlib.import_module(_NAME + '.H3CounterfactualRouter.guards')
observer = importlib.import_module(_NAME + '.H3CounterfactualRouter.observer')
