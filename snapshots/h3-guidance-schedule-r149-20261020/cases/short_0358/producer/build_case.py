"""Prepare only short_0358 from sealed R149 runtime and R148 historical inputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
TEMPLATE = PROJECT / "cases/short_0252"
HISTORY = Path("/Users/researcher/DevProjects/h3-timing-phase-combined-r148-20261020/cases/short_0358")
SAM = PROJECT / "fallback_host9/cases/05_real_megumi_v"
EVAL = Path("/Users/researcher/DevProjects/h3-timing-phase-combined-eval-r148-20261020")
REMOTE = "/data4/researcher/h3_runs/guidance_schedule_r149_20261020/cases/short_0358"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(relative, value):
    p = ROOT / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def cp(source, relative):
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


assert not (ROOT / "configs").exists(), "preserve an existing prepared case"
template_seal = read(TEMPLATE / "deploy_manifest.json")
for name, record in template_seal["files"].items():
    assert sha(TEMPLATE / name) == record["sha256"], name
    if name.startswith(("configs/graphs/", "configs/prompts/", "design/", "inputs/")):
        continue
    if name in {"configs/runtime_device_rebind.json", "audit/INHERITANCE.json"}:
        continue
    cp(TEMPLATE / name, name)
for folder in ("logs", "processes", "output", "input", "audit/router", "audit/x0"):
    (ROOT / folder).mkdir(parents=True, exist_ok=True)

old = read(HISTORY / "configs/scientific_contract.json")
parent_case = old["cases"][0]
old_graph = HISTORY / "configs/graphs" / (parent_case["run_id"] + ".json")
for name in ("design/parent_native_graph.json", "design/conditioning.json",
             "design/HISTORICAL_FIXED.json", "design/R122_actual_native_router.json",
             "design/H3_model.py", "design/R17_core.py",
             "configs/CONDITION_CACHE.json", "configs/input_hashes.json"):
    cp(HISTORY / name, name)
cp(old_graph, "design/parent_cached_graph.json")
cp(HISTORY / "inputs/short_0358_video.mp4", "inputs/short_0358_video.mp4")
(ROOT / "configs/prompts").mkdir(exist_ok=True)
(ROOT / "configs/prompts/short_0358.txt").write_text(parent_case["prompt"])

runtime = read(ROOT / "configs/runtime.json")
runtime.update(remote_root=REMOTE, port=8642, profile="r149_short_0358_schedule_only",
               profile_scope="Four fixed same-bin schedule arms; exact R123 cached inputs and noise; phase0")
write("configs/runtime.json", runtime)
science = read(ROOT / "configs/scientific_contract.json")
science["cases"] = []
sigma = [float(x) for x in read(old_graph)["9"]["inputs"]["sigmas"].split(",")]
schedules = {"early": list(range(9)), "late": list(range(11, 20)),
             "split": list(range(4)) + list(range(15, 20)), "global_weak": list(range(20))}
for arm, steps in schedules.items():
    case = copy.deepcopy(parent_case)
    case.update(run_id=f"r149_short_0358_seed2026101701_{arm}", arm=arm,
                physical_query_window=[0, 104], steps_zero_based=steps,
                phase_displacement=0, alpha=.25 if arm == "global_weak" else 1.)
    case["sigma_selected"] = [{"step": s, "sigma": sigma[s], "sigma_next": sigma[s+1]} for s in steps]
    case["sum_abs_delta_sigma"] = sum(abs(sigma[s]-sigma[s+1]) for s in steps)
    if arm == "global_weak":
        case["comparison_scope"] = "All20 denoise steps, alpha0.25, all105 valid source frames"
    science["cases"].append(case)
science.update(case_order=[c["run_id"] for c in science["cases"]], source_ids=["short_0358"],
               arms=list(schedules), historical_runtime=old["historical_runtime"],
               parent_cached_graph_sha256=sha(old_graph),
               parent_r148_seal_sha256=sha(HISTORY / "deploy_manifest.json"))
for k in ("conditioning_sha256", "historical_shared_run", "noise_pair_id",
          "parent_noise_file", "parent_noise_sha256"):
    science[k] = old[k]
write("configs/scientific_contract.json", science)
write("configs/queue.json", {"jobs": science["case_order"], "finalize": True})
storage = read(ROOT / "configs/storage_policy.json")
storage["estimate_status"] = "Four final AV outputs and20-step latent audits; retain20GiB disk gate"
write("configs/storage_policy.json", storage)

# Preserve four-role video-only reconstruction; copy only verified publication helpers.
cache_path = ROOT / "extensions/H3CachedCondition/__init__.py"
cache = cache_path.read_text()
sam_cache = (SAM / "extensions/H3CachedCondition/__init__.py").read_text()
helper = sam_cache[sam_cache.index("def publish_blob("):sam_cache.index("\ndef signature(")]
metadata = sam_cache[sam_cache.index("def publish_metadata("):sam_cache.index("\n\nclass H3CachedReferenceConditioning")]
cache = cache.replace("import os\n", "import os\nimport errno\nimport shutil\nimport uuid\n")
cache = cache.replace("\ndef signature(", "\n" + helper + "\ndef signature(", 1)
start, end = cache.index("def publish_metadata("), cache.index("\n\nclass H3CachedReferenceConditioning")
cache = cache[:start] + metadata + cache[end:]
cache_path.write_text(cache)
cp(SAM / "tests/test_cross_device_cache.py", "tests/test_cross_device_cache.py")

contract_path = ROOT / "scripts/r132_contract.py"
contract = contract_path.read_text()
contract = contract.replace('"05_real_megumi_v": (2026101311, 141, [50, 65])}',
                            '"05_real_megumi_v": (2026101311, 141, [50, 65]),\n'
                            '                    "short_0358": (2026101701, 107, [0, 104])}')
assert '"short_0358": (2026101701, 107, [0, 104])' in contract
contract = contract.replace("        os.link(source, target)\n",
    "        try: os.link(source, target)\n"
    "        except OSError as error:\n"
    "            import errno, shutil\n"
    "            if error.errno != errno.EXDEV: raise\n"
    "            shutil.copy2(source, target)\n")
contract_path.write_text(contract)
runner = ROOT / "audit/root_run_batch.py"
runner.write_text(runner.read_text().replace("analysis/postrun/short_0252/", "analysis/postrun/short_0358/"))

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("r132_contract", contract_path)
module = importlib.util.module_from_spec(spec)
sys.modules["r132_contract"] = module
spec.loader.exec_module(module)
for c in science["cases"]:
    write("configs/graphs/" + c["run_id"] + ".json", module.expected_graph(c["run_id"], ROOT))
module.registry(ROOT)

evaluation = next(c for c in read(EVAL / "EVALUATION_MANIFEST.json")["cases"]
                  if c["source_id"] == "short_0358")
review = read(EVAL / "review/short_0358/REVIEW.json")
write("design/HISTORICAL_TIMING.json",
      {"source": str(EVAL / "review/short_0358/REVIEW.json"),
       "source_sha256": sha(EVAL / "review/short_0358/REVIEW.json"),
       "events": review["events"], "official_MF": evaluation["official_MF"],
       "timing": evaluation["timing"], "prompt_format": "historical six-section full_context",
       "prompt_sha256": evaluation["prompt_sha256"],
       "task_verdict": review["task_verdict"],
       "reason": "Compare schedule while retaining the exact completed historical edit."})
write("audit/INHERITANCE.json",
      {"schema": "r149-short0358-inheritance-v1", "parent_root": str(HISTORY),
       "parent_seal_sha256": sha(HISTORY / "deploy_manifest.json"),
       "runtime_template": str(TEMPLATE), "runtime_template_seal_sha256": sha(TEMPLATE / "deploy_manifest.json"),
       "unchanged_numerical_files": read(ROOT / "configs/numerical_reuse.json"),
       "method": "Original fixed RouterState/EventBlockPatch; schedule membership only; phase0",
       "copy_fallback": "H3CachedCondition publication verifies SHA; noise link EXDEV copies and verifies SHA",
       "old_fixed_steps_reused": list(range(6, 15)),
       "requires_predecessor_release": "short_0252 attempt5 COMPLETE and exact service release before launch",
       "created_unix": time.time()})
from execution_gate import seal
result = seal(ROOT)
print(json.dumps({"case": str(ROOT), "seal_sha256": sha(ROOT / "deploy_manifest.json"),
                  "sealed_files": len(result["files"]), "jobs": science["case_order"]}))
