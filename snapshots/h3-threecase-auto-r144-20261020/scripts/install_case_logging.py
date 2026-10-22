"""Install a read-only summary hook without touching the numerical controller."""
import shutil
from pathlib import Path
from prepare_cases import ROOT, BASE, sha, read, write, replace


def install(root):
    root = Path(root)
    shutil.copyfile(ROOT / "scripts/summarize_steps.py", root / "scripts/summarize_steps.py")
    controller = root / "scripts/root_run_online.py"
    old = "done,row=check(owner)\n"
    new = (
        "done,row=check(owner)\n"
        "  from summarize_steps import summarize\n"
        "  try:atomic(ROOT/'audit/AUTO_STEP_LOG.json',summarize(ROOT))\n"
        "  except json.JSONDecodeError:pass  # atomic producer audit replacement may be in flight\n"
    )
    if old in controller.read_text():
        replace(controller, old, new)
    provenance = read(root / "audit/INHERITANCE.json")
    rel = "scripts/root_run_online.py"
    provenance["unchanged_numerics"].pop(rel, None)
    provenance["metadata_lifecycle_adaptations"][rel] = {
        "parent_sha256": sha(BASE / rel), "sha256": sha(controller),
        "change": "read-only compact log after existing status sample"}
    write(root / "audit/INHERITANCE.json", provenance)
    shutil.copyfile(BASE / "tests/test_visible_feedback.py", root / "tests/test_visible_feedback.py")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    install(ROOT / "cases" / args.case)
