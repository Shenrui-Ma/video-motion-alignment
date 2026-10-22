"""Read-only, hash-pinned imports of the existing H3Study implementation."""
from functools import lru_cache
import hashlib
import importlib
import os
from pathlib import Path
import sys
import types


SOURCE_HASHES = {
    "core.py": "2dba7d615092491ad5b696b81ae2c0d41e9cae3760046aeefbdf33ad0d543691",
    "layout.py": "d71a0a34956c1c57e534f906df3dc954bc6b4ab02b33f78f0b0ba913e6acca08",
    "schedule.py": "8cc187efc98c00280c321368c7471066970ae2aa633f52dd885160dc4190ae89",
}


@lru_cache(maxsize=1)
def load_frozen():
    explicit = os.environ.get("H3_COVERAGE_FROZEN_ROOT")
    candidates = ([Path(explicit)] if explicit else [
        Path(__file__).resolve().parents[2] / "inference/package/custom_nodes/H3Study",
        Path(__file__).resolve().parent.parent / "H3Study",
    ])
    root = next((p.resolve() for p in candidates if (p / "core.py").is_file()), None)
    if root is None:
        raise FileNotFoundError("Set H3_COVERAGE_FROZEN_ROOT to the frozen H3Study directory")
    for name, expected in SOURCE_HASHES.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Frozen dependency hash mismatch: {root / name}")
    name = "_h3_coverage_frozen_" + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(root)]
        package.__package__ = name
        sys.modules[name] = package
    # Import only the three implementation modules, without executing node __init__.
    return types.SimpleNamespace(
        core=importlib.import_module(name + ".core"),
        layout=importlib.import_module(name + ".layout"),
        schedule=importlib.import_module(name + ".schedule"),
        root=str(root), hashes=dict(SOURCE_HASHES),
    )
