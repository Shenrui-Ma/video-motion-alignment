"""Remote CPU-only attachment of pre-existing runtime/cache; never downloads."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = json.loads((ROOT / "configs/RUNTIME.json").read_text())
assert str(ROOT) == runtime["remote_root"], "Run only in the bound scoring directory"
plan = json.loads((ROOT / "audit/REMOTE_REUSE_PLAN.json").read_text())
for relative, existing in plan.items():
    source, destination = Path(existing), ROOT / relative
    assert source.exists(), f"Existing server artifact missing: {source}"
    assert destination.is_relative_to(ROOT) and ".." not in Path(relative).parts
    destination.parent.mkdir(parents=True, exist_ok=True)
    if relative == "runtime":
        assert source.is_dir()
        if not destination.exists():
            destination.symlink_to(source, target_is_directory=True)
        assert destination.resolve() == source.resolve()
    else:
        assert source.is_file()
        if not destination.exists():
            os.link(source, destination)
print(json.dumps({"passed": True, "existing_links": len(plan), "downloaded": False, "GPU_started": False}))
