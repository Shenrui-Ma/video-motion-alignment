"""CPU-only reuse of the frozen R133 controller for three actual historical pairs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "h3-timing-oxygen-online-r133-20261020"
REMOTE = Path("/data4/researcher/h3_runs/threecase_auto_r144_20261020")
ORDER = ("short_0358", "long_0039", "long_0059")
DECODER = "GPU-REDACTED"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(data)
    os.replace(temporary, path)


def replace(path, old, new):
    text = path.read_text()
    if old not in text:
        raise ValueError(f"adaptation target absent: {path}: {old[:80]}")
    write(path, text.replace(old, new))


def copy_record(record, destination):
    source = Path(record["file"])
    assert sha(source) == record["sha256"], source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def actual_binding(binding, remote):
    gate = read(binding["actual_pair_gate"]["file"])
    run = binding["runs"]["native"]["run_id"]
    return {
        "inventory_id": binding["inventory_id"],
        "source_id": binding["source_id"],
        "producer_host_alias": binding["producer_host_alias"],
        "producer_remote": binding["producer_remote"],
        "parent_run": run,
        "parent_shared_run": read(binding["runs"]["native"]["actual_graph"]["file"])["51"]["inputs"]["source_run_id"],
        "pair_id": read(binding["runs"]["native"]["actual_graph"]["file"])["6"]["inputs"]["pair_id"],
        "prompt_sha256": binding["prompt_sha256"],
        "seed": binding["seed"],
        "source": binding["source"],
        "geometry": binding["geometry"],
        "native": binding["runs"]["native"],
        "fixed": binding["runs"]["forced"],
        "parent_gate_sha256": binding["actual_pair_gate"]["sha256"],
        "same_host": binding["producer_host_alias"] == "H3_SERVER_B",
        "cross_host_policy": "Record exact input differences; do not add another Native. Exact original AV noise is mandatory.",
        "condition_tensor_files": gate["condition_tensor_files"],
        "auto_remote_root": str(remote),
    }


def create_case(sid):
    root = ROOT / "cases" / sid
    if root.exists():
        raise ValueError(f"refuse replacing an existing case: {root}")
    b = read(ROOT / "input_audit" / (sid + "_BINDING.json"))
    remote = REMOTE / "cases" / sid
    run = f"r144_{sid}_seed{b['seed']}_visible_only"
    for folder in ("scripts", "extensions", "analysis/postrun", "source_snapshot"):
        for source in (BASE / folder).rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                destination = root / source.relative_to(BASE)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
    for folder in ("prepared_parent", "inputs", "input", "output", "temp", "user", "processes",
                   "logs", "audit", "tests", "design", "configs/graphs", "configs/prompts"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for name in ("expected_checkpoint_hashes.json", "observer_external_bindings.json",
                 "parent_core_hashes.json", "cgroup_policy.json", "decoder_memory_profile.json"):
        shutil.copyfile(BASE / "configs" / name, root / "configs" / name)
    parent_graph = read(b["runs"]["native"]["actual_graph"]["file"])
    copy_record(b["runs"]["native"]["actual_graph"], root / "configs/PARENT_GRAPH.json")
    copy_record(b["actual_pair_gate"], root / "configs/PARENT_PAIR_GATE.json")
    write(root / "configs/HISTORICAL_BINDING.json", actual_binding(b, remote))
    # Collection is authoritative for opaque binding_NN.json names.
    collection = read(Path(b["consumer"]) / "incoming_pairs" / sid / "COLLECTION.json")
    intake = Path(b["consumer"]) / "incoming_pairs" / sid
    manifest_sha = b["runs"]["native"]["binding_artifacts"][f"audit/x0/{b['runs']['native']['run_id']}/manifest.json"]
    captures = [p for p in intake.glob("binding_*.json") if sha(p) == manifest_sha]
    assert len(captures) == 1, "actual Native capture manifest absent"
    shutil.copyfile(captures[0], root / "configs/PARENT_CAPTURES.json")
    for role, name in (("source", f"{sid}_video.mp4"), ("provenance", f"{sid}_provenance.json")):
        copy_record(b[role], root / "inputs" / name)
    write(root / "configs/input_hashes.json", {
        f"{sid}_video.mp4": b["source"]["sha256"],
        f"{sid}_provenance.json": b["provenance"]["sha256"],
    })
    write(root / "configs/prompts" / (sid + ".txt"), b["prompt"])
    geo = {"width": b["geometry"]["width"], "height": b["geometry"]["height"],
           "frames": b["geometry"]["sampled_frames"], "fps": b["geometry"]["fps"]}
    case = {
        "run_id": run, "source_id": sid, "seed": b["seed"], "prompt": b["prompt"],
        "inventory_id": b["inventory_id"], "arm": "visible_only",
        "geometry": geo, "valid_frame_count": b["geometry"]["valid_frames"],
        "evaluation_crop_xywh": b["geometry"]["crop_xywh"],
        "video": f"{sid}_video.mp4", "video_sha256": b["source"]["sha256"],
        "provenance": f"{sid}_provenance.json", "provenance_sha256": b["provenance"]["sha256"],
        "reference_video_count": 1, "reference_image_count": 0,
        "parent_graph": "configs/PARENT_GRAPH.json", "parent_graph_sha256": sha(root / "configs/PARENT_GRAPH.json"),
        "parent_run": b["runs"]["native"]["run_id"], "parent_root": b["producer_remote"],
        "parent_conditioning": "prepared_parent/conditioning.json", "parent_noise": "prepared_parent/noise.json",
        "parent_captures": "configs/PARENT_CAPTURES.json", "parent_file_inventory": "prepared_parent/FILE_INVENTORY.json",
        "source_pose_path": "configs/source.pose.json", "source_pose_sha256": None,
        "source_pose_status": "PENDING_SOURCE_ONLY_CPU_POSE",
    }
    protocol = read(BASE / "configs/protocol.json")
    protocol.update(schema="r144-original-visible-only-v1", scope="Actual auto output for one historical pair",
                    cases=[case], geometry=geo, GPU_launch_authorized=False,
                    preparation_status="CPU_SOURCE_POSE_PENDING")
    protocol["observer"]["valid_frame_count"] = case["valid_frame_count"]
    protocol["resources"].update(decoder_uuid=DECODER, CPU_lock=str(REMOTE / "audit/pose.lock"),
                                 capacity_status="107 measured; 158 pending explicit capacity review")
    protocol["prefix"] = {"availability": "actual historical Native captures", "comparison": "exact through first ON",
                          "parent_gate_sha256": sha(root / "configs/PARENT_PAIR_GATE.json")}
    protocol["inherited_rule"] = {"parent": "R133 original confidence-only visible_only",
                                  "detector_policy_actuator_unchanged": True,
                                  "centered_motion_gate": False, "content_boundary_filter": False}
    protocol["person_selection"] = {"kind": "source-specified spatial selector",
                                     "selected_bbox_center_x_fraction": None,
                                     "status": "PENDING_SOURCE_REVIEW"}
    protocol["evaluation"] = {"valid_frames": case["valid_frame_count"], "existing_native_and_fixed_reused": True,
                               "source_content_valid_visibility_is_separate_audit": True}
    write(root / "configs/protocol.json", protocol)
    science = read(BASE / "configs/scientific_contract.json")
    science.update(cases=[case], case_order=[run], parent_gate_sha256=protocol["prefix"]["parent_gate_sha256"])
    write(root / "configs/scientific_contract.json", science)
    write(root / "configs/queue.json", {"jobs": [run], "finalize": True})
    write(root / "configs/PARENT_CLOSURE.json", {"ready": False, "status": "MATERIALIZATION_PENDING"})
    runtime = read(BASE / "configs/runtime.json")
    runtime.update(remote_root=str(remote), port=8644, decoder_gpu_uuid=DECODER, decoder_expected_gpu_index=3,
                   profile_scope="R144 original automatic per-step Native-first; no fixed schedule or centered gate")
    write(root / "configs/runtime.json", runtime)
    admission = read(BASE / "configs/admission_template.json")
    admission["fixed_fields"]["decoder_gpu_uuid"] = DECODER
    write(root / "configs/admission_template.json", admission)
    write(root / "configs/admission.json", dict(admission["fixed_fields"], permitted_compute_processes=[],
                                                root_live_review_required=True, ready_for_launch=False))
    if geo["frames"] == 158:
        profile = read(root / "configs/decoder_memory_profile.json")
        profile.update(status="UNMEASURED_158_REQUIRES_RESOURCE_REVIEW", geometry=geo,
                       historical_scope="Only 107-frame 6027214848-byte reserved peak is verified; not a 158-frame measurement")
        profile.pop("actual_precheck_max_reserved_bytes")
        write(root / "configs/decoder_memory_profile.json", profile)
    # Metadata/lifecycle adapters; the detector, policy, actuator, and same-state core remain byte-identical.
    contract = root / "scripts/r86_contract.py"
    replace(contract, "RUN='r133_short_0252_seed2026101703_visible_only'", f"RUN={run!r}")
    replace(contract, "SOURCES=('short_0252',)", f"SOURCES=({sid!r},)")
    replace(contract, "c['source_id']=='short_0252' and c['run_id']==RUN and c['seed']==2026101703",
            f"c['source_id']=={sid!r} and c['run_id']==RUN and c['seed']=={b['seed']}")
    replace(contract, "c['geometry']=={'width':1312,'height':736,'frames':107,'fps':24} and c['valid_frame_count']==98",
            f"c['geometry']=={geo!r} and c['valid_frame_count']=={case['valid_frame_count']}")
    replace(contract, "configs/prompts/short_0252.txt", f"configs/prompts/{sid}.txt")
    replace(contract, "require(p['person_selection']['selected_bbox_center_x_fraction']==[.4,.75],'source-specified spatial selector differs')",
            "bounds=p['person_selection']['selected_bbox_center_x_fraction']; require(bounds is None or (len(bounds)==2 and 0<=bounds[0]<bounds[1]<=1),'invalid source-specified identity bounds')")
    graph = copy.deepcopy(parent_graph)
    for node, key, folder in (("5", "audit_dir", "audit"), ("6", "audit_dir", "audit"),
                             ("51", "source_audit_dir", "audit"), ("52", "output_dir", "audit/x0")):
        graph[node]["inputs"][key] = str(remote / folder)
    for node in ("6", "51", "52"):
        graph[node]["inputs"]["run_id"] = run
    graph["14"]["inputs"]["filename_prefix"] = run
    graph["50"] = {"class_type": "H3AutomaticWindowRouter",
                   "inputs": {"model": ["41", 0], "positive": ["51", 0],
                              "run_id": run, "audit_dir": str(remote / "audit/counterfactual")}}
    write(root / "configs/graphs" / (run + ".json"), graph)
    replace(root / "extensions/H3PairAudit/__init__.py",
            "'r113_'+row['case']['source_id']+'_shared'", repr(parent_graph["51"]["inputs"]["source_run_id"]))
    transport = root / "extensions/H3AutomaticWindowRouter/transport.py"
    replace(transport, "GPU-REDACTED", DECODER)
    replace(transport, str(Path(read(BASE / "configs/runtime.json")["remote_root"])), str(remote))
    replace(transport, "PROTOCOL_SHA='5f662eb0f3dfd6e8c9e954118a15ff1a4d028f0062f3e0406ea87e57fbefa320'",
            f"PROTOCOL_SHA={sha(root / 'configs/protocol.json')!r}")
    # R138's extra concurrent-owned-decoder exclusion, restricted to GPU3 without fallback.
    replace(transport, "planned=owned|{DECODER_UUID}|({MAIN_UUID} if parent is not None else set())",
            "if parent is not None and any(row['gpu_uuid']!=MAIN_UUID and entries[row['pid']]['uid']==os.getuid() and not preserved_user_process(row,entries[row['pid']]) for row in processes):\n  raise ResourceUnavailable('another owned research CUDA process is active outside main',snapshot)\n planned=owned|{DECODER_UUID}|({MAIN_UUID} if parent is not None else set())")
    pose = root / "scripts/pose_live_child.py"
    replace(pose, "filtered,rejected=adult_only(raw,geometry.video_geometry)",
            "bounds=protocol['person_selection']['selected_bbox_center_x_fraction'];t.require(bounds is not None,'source identity selection pending')\n   filtered,rejected=adult_only(raw,geometry.video_geometry,bounds)")
    replace(pose, "'bounds':[.4,.75]", "'bounds':bounds")
    replace(root / "scripts/execution_contract.py", repr(read(BASE / "configs/protocol.json")["cases"][0]["parent_root"]),
            repr(b["producer_remote"]))
    replace(root / "scripts/verify_parent_payloads.py", "'r113_short_0252_seed2026101703_noise.pt'",
            repr(parent_graph["6"]["inputs"]["pair_id"] + "_noise.pt"))
    materialize = root / "scripts/materialize_parent.py"
    replace(materialize, "native['solver_updates']", "native['Euler_updates']")
    replace(materialize, "len(inventory)==23", "len(inventory)==21")
    replace(materialize, "'r113_short_0252_seed2026101703_noise.pt'",
            repr(parent_graph["6"]["inputs"]["pair_id"] + "_noise.pt"))
    replace(materialize, "root=Path(root);registry(root);", "root=Path(root);registry(root);")
    replace(materialize, "for row in native['snapshots']:", "require((root/'configs/source.pose.json').is_file(),'source pose pending')\n for row in native['snapshots']:")
    preflight = root / "scripts/preflight.py"
    replace(preflight, "if live:\n", "if live:\n  p=read(root/'configs/protocol.json');c=p['cases'][0]\n  require(c['source_pose_sha256'] is not None and p['person_selection']['selected_bbox_center_x_fraction'] is not None,'source pose/identity binding pending')\n  require(sha(root/c['source_pose_path'])==c['source_pose_sha256'],'source pose changed')\n")
    replace(preflight, "'spatial_selection':'source-specified .40-.75'", "'spatial_selection':read(root/'configs/protocol.json')['person_selection']")
    post = root / "analysis/postrun/verify_online.py"
    replace(post, "adult_only(read(raw_path),read(ROOT/'configs/protocol.json')['cases'][0]['geometry'])",
            "adult_only(read(raw_path),read(ROOT/'configs/protocol.json')['cases'][0]['geometry'],read(ROOT/'configs/protocol.json')['person_selection']['selected_bbox_center_x_fraction'])")
    replace(post, "[1312,736,'24/1','107']", f"[{geo['width']},{geo['height']},'24/1',{str(geo['frames'])!r}]")
    replace(post, "valid_frames=98,spatial_selection='source-specified xcenter .40-.75'",
            f"valid_frames={case['valid_frame_count']},spatial_selection=read(ROOT/'configs/protocol.json')['person_selection']")
    replace(root / "scripts/verify_completed.py", "'Native_reused_from_R113_seed1703':True", "'existing_case_Native_reused':True")
    # Do not inherit old output evidence or launch approval.
    unchanged = {}
    adapted = {}
    for folder in ("scripts", "extensions", "analysis/postrun", "source_snapshot"):
        for dest in (root / folder).rglob("*.py"):
            rel = str(dest.relative_to(root))
            source = BASE / rel
            if sha(dest) == sha(source):
                unchanged[rel] = {"sha256": sha(dest), "parent": str(source)}
            else:
                adapted[rel] = {"parent_sha256": sha(source), "sha256": sha(dest)}
    write(root / "audit/INHERITANCE.json", {"parent": str(BASE), "unchanged_numerics": unchanged,
                                             "metadata_lifecycle_adaptations": adapted,
                                             "centered_gate": False, "content_boundary_filter": False})
    subprocess.run([sys.executable, str(root / "scripts/preflight.py")], check=True)
    subprocess.run([sys.executable, str(root / "scripts/execution_gate.py"), "seal"], check=True)
    return {"source_id": sid, "root": str(root), "remote_root": str(remote), "run_id": run,
            "status": "CPU_PREPARED_SOURCE_POSE_PENDING", "same_host": b["producer_host_alias"] == "H3_SERVER_B",
            "seal_sha256": sha(root / "deploy_manifest.json"), "sampled_frames": geo["frames"],
            "valid_frames": case["valid_frame_count"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=ORDER)
    args = parser.parse_args()
    rows = [create_case(sid) for sid in ((args.case,) if args.case else ORDER)]
    write(ROOT / "audit/CPU_CASES_CREATED.json", rows)
    print(json.dumps(rows, indent=2))
