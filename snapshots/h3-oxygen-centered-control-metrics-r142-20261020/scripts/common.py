"""R142 local-only boundary, reusing the pinned R133/R120 CPU primitives."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "configs/CONTRACT.json").read_text())


def load_helper(name):
    b = CONTRACT["helpers"][name]
    p = Path(b["file"])
    if hashlib.sha256(p.read_bytes()).hexdigest() != b["sha256"]:
        raise ValueError("shared helper changed: " + str(p))
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_helper("r133_common")
read, sha, bound, require = base.read, base.sha, base.bound, base.require


def save(path, value):
    path = Path(path)
    require(path.resolve().is_relative_to(ROOT), "write outside consumer")
    require(not path.exists(), "immutable output already exists: " + str(path))
    base.save(path, value)


def link(source, destination):
    source, destination = Path(source), Path(destination)
    require(destination.resolve().is_relative_to(ROOT), "link outside consumer")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        os.link(source, destination)
    require(sha(source) == sha(destination), "existing link differs")


def validate_static():
    c = CONTRACT
    freeze = ROOT/"CONSUMER_SEAL.json"
    if freeze.exists():
        for rel,digest in read(freeze)["files"].items():
            require(sha(ROOT/rel)==digest,"consumer source changed: "+rel)
    for key in ("producer_seal", "protocol", "graph", "noise", "runtime", "historical_handoff", "mf_template_seal"):
        require(sha(c[key]["file"]) == c[key]["sha256"], key + " changed")
    producer = Path(c["producer_local"])
    for rel, row in read(c["producer_seal"]["file"])["files"].items():
        require(sha(producer / rel) == row["sha256"], "producer file changed: " + rel)
    for role, b in c["historical"].items():
        require(sha(b["file"]) == b["sha256"], "historical media changed: " + role)
    case = c["case"]
    require(case["source_id"] == "short_0252" and case["seed"] == 2026101703, "source/seed")
    require(case["geometry"] == dict(width=1312, height=736, frames=107, fps=24), "domain")
    require(case["video_sha256"] == c["historical"]["source"]["sha256"], "source pixels")
    historical = read(c["historical_handoff"]["file"])
    base.check_bindings(read(ROOT/"configs/EVALUATION_PLAN.json"))
    base.check_bindings(read(ROOT/"prepared/MF_ROUTE.json")["historical_scores"])
    base.check_bindings(read(ROOT/"prepared/MF_ROUTE.json")["source_cache_proof"])
    require(read(c["graph"]["file"])["5"]["inputs"]["prompt"] == case["prompt"]
            == historical["actual_prompt"]["text"], "historical prompt differs")
    return c


def actual():
    validate_static()
    d = ROOT / "incoming/actual"
    m = read(d / "COLLECTION.json")
    for rel, digest in m["files"].items():
        require(sha(d / rel) == digest, "intake changed: " + rel)
    from consume import verify
    verify(d)
    return m
