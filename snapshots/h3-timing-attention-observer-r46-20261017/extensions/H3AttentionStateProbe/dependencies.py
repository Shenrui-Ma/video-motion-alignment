"""Load unchanged sibling extensions without changing sys.path or process state."""
import hashlib
import importlib
from pathlib import Path
import sys
import types

_ROOT = Path(__file__).resolve().parent.parent
_NAME = "_h3_feedback_dependencies_" + hashlib.sha256(str(_ROOT).encode()).hexdigest()[:16]
if _NAME not in sys.modules:
    package = types.ModuleType(_NAME)
    package.__path__ = [str(_ROOT)]
    sys.modules[_NAME] = package

router = importlib.import_module(_NAME + ".H3TemporalRouter.core")
layout = importlib.import_module(_NAME + ".H3TemporalRouter.layout")
readout = importlib.import_module(_NAME + ".H3X0Readout.core")
