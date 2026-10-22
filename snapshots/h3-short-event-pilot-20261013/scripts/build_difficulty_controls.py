#!/usr/bin/env python3
"""Prepare four conditional same-source clothing controls locally only.

No server calls, queue changes, input edits or overwrite of different content.
The root agent must separately decide whether the registered trigger occurred.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from verify_archive import normalized_main_graph, primary_sink, source_nodes

SOURCE = "02_celebrate_thumbs"
OLD_EDIT = "Edit the source video by changing only the man's mustard yellow hoodie to a solid bright royal blue hoodie."
NEW_EDIT = ("Edit the source video by replacing only the man's mustard yellow hoodie with a charcoal "
            "tailored blazer with notched lapels over a plain white collared dress shirt. Keep both hands uncovered.")


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def node_of_type(graph, class_type):
    matches = [key for key, node in graph.items() if node.get("class_type") == class_type]
    if len(matches) != 1:
        raise ValueError("expected exactly one " + class_type)
    return matches[0]


def changed_paths(left, right, prefix=""):
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            path = prefix + "." + key if prefix else key
            if key not in left or key not in right:
                result.append(path)
            else:
                result.extend(changed_paths(left[key], right[key], path))
        return result
    return [] if left == right else [prefix]


def prepare(root):
    root = Path(root)
    conditional_path = root / "configs/conditional_difficulty_control.json"
    conditional_bytes = conditional_path.read_bytes()
    conditional = json.loads(conditional_bytes)
    if conditional.get("same_source") != SOURCE or conditional.get("max_additional_outputs") != 4:
        raise ValueError("conditional plan no longer matches the bounded four-output design")
    if conditional.get("seeds") != [2026101301, 2026101302]:
        raise ValueError("conditional plan seeds changed")
    metadata_path = root / "inputs" / (SOURCE + ".json")
    metadata_bytes = metadata_path.read_bytes()
    addition = json.loads(metadata_bytes)["prompts"]["B_addition"]
    artifacts, jobs, checks, bases = {}, [], [], {}
    for seed_index, expected_seed in ((1, 2026101301), (2, 2026101302)):
        graphs = {}
        ids = {arm: f"{SOURCE}_{arm}_s{seed_index}" for arm in "abcd"}
        for original_arm in "ab":
            path = root / "configs" / (ids[original_arm] + ".json")
            raw = path.read_bytes()
            graphs[original_arm] = json.loads(raw)
            bases[ids[original_arm]] = {"path": str(path), "sha256": sha(raw)}
        if normalized_main_graph(graphs["a"], ids["a"]) != normalized_main_graph(graphs["b"], ids["b"]):
            raise ValueError("primary A/B inference settings already differ")
        ref_key = node_of_type(graphs["a"], "H3EventAuditReference")
        noise_key = node_of_type(graphs["a"], "H3EventAuditNoise")
        a_prompt = graphs["a"][ref_key]["inputs"]["prompt"]
        b_prompt = graphs["b"][ref_key]["inputs"]["prompt"]
        if b_prompt.count(addition) != 1 or b_prompt.replace(" " + addition, "", 1) != a_prompt:
            raise ValueError("original B is not exactly A plus the recorded B_addition")
        for original_arm, control_arm in (("a", "c"), ("b", "d")):
            original = graphs[original_arm]
            sink = primary_sink(original, ids[original_arm])
            keep = source_nodes(original, sink)
            removed = sorted(set(original) - keep)
            if not set(removed).issubset({"30", "31", "32", "33", "34"}):
                raise ValueError("unexpected unreachable nodes beyond the known diagnostic branches")
            graph = {key: copy.deepcopy(value) for key, value in original.items() if key in keep}
            prompt = graph[ref_key]["inputs"]["prompt"]
            if prompt.count(OLD_EDIT) != 1:
                raise ValueError("original edit phrase is absent or ambiguous")
            graph[ref_key]["inputs"]["prompt"] = prompt.replace(OLD_EDIT, NEW_EDIT, 1)
            graph[ref_key]["inputs"]["run_id"] = ids[control_arm]
            graph[noise_key]["inputs"]["run_id"] = ids[control_arm]
            graph[sink]["inputs"]["filename_prefix"] = ids[control_arm]
            if normalized_main_graph(graph, ids[control_arm]) != normalized_main_graph(original, ids[original_arm]):
                raise ValueError("control altered a frozen primary inference setting")
            ref, noise = graph[ref_key]["inputs"], graph[noise_key]["inputs"]
            sigma_key = node_of_type(graph, "ManualSigmas")
            sampler_key = node_of_type(graph, "KSamplerSelect")
            source_key = node_of_type(graph, "LoadVideo")
            shift_key = node_of_type(graph, "MiniMaxH3SigmaShift")
            sigmas = graph[sigma_key]["inputs"]["sigmas"].split(",")
            if len(sigmas) != 21 or float(sigmas[0]) != 1 or float(sigmas[-1]) != 0:
                raise ValueError("expected frozen 20-step sigma schedule")
            if graph[sampler_key]["inputs"]["sampler_name"] != "euler":
                raise ValueError("expected Euler sampler")
            if graph[source_key]["inputs"]["file"] != SOURCE + ".mp4":
                raise ValueError("source changed")
            if noise["noise_seed"] != expected_seed or noise["pair_id"] != f"{SOURCE}_s{seed_index}":
                raise ValueError("actual noise pairing changed")
            if (ref["width"], ref["height"], ref["length"], ref["semantic_fps"], ref["phase_frames"]) != (1312, 736, 107, 2, 0):
                raise ValueError("geometry or semantic observations changed")
            shift = graph[shift_key]["inputs"]
            if shift["shift_video"] != 12 or shift["shift_audio"] != 3 or shift["model"] != ["1", 0]:
                raise ValueError("native SDPA model wiring or sigma shift changed")
            if any("lora" in node["class_type"].lower() or "sage" in node["class_type"].lower()
                   or node["class_type"] == "ModelAttentionBackend" for node in graph.values()):
                raise ValueError("unexpected LoRA/attention patch")
            graphs[control_arm] = graph
            artifacts[ids[control_arm] + ".json"] = encoded(graph)
            peer = "d" if control_arm == "c" else "c"
            jobs.append({"run_id": ids[control_arm], "source_id": SOURCE,
                         "description": ("Secondary exploratory clothing-structure control: charcoal tailored blazer with notched lapels "
                                         "over a plain white collared dress shirt, hands uncovered; "
                                         + ("generic motion preservation." if control_arm == "c" else "same edit plus the original explicit double-thumbs-up preservation instruction.")),
                         "paired_noise_id": noise["pair_id"],
                         "comparison_to": [ids["a"], ids["b"], ids[peer]],
                         "independent_sample": False})
            checks.append({"run_id": ids[control_arm], "primary_template": ids[original_arm],
                           "main_graph_matches_primary_except_prompt_and_labels": True,
                           "removed_diagnostic_nodes": removed, "seed": expected_seed,
                           "paired_noise_id": noise["pair_id"], "steps": 20})
        c, d = graphs["c"], graphs["d"]
        sink = primary_sink(c, ids["c"])
        allowed = sorted([f"{ref_key}.inputs.prompt", f"{ref_key}.inputs.run_id",
                          f"{noise_key}.inputs.run_id", f"{sink}.inputs.filename_prefix"])
        differences = changed_paths(c, d)
        if differences != allowed:
            raise ValueError("C/D differences exceed the exact four allowed fields: " + repr(differences))
        if d[ref_key]["inputs"]["prompt"].replace(" " + addition, "", 1) != c[ref_key]["inputs"]["prompt"]:
            raise ValueError("D does not preserve the original exact B_addition")
        for check in checks[-2:]:
            check["cd_exact_changed_paths"] = differences
    artifacts["controls.json"] = encoded({"status": "prepared_only_not_queued",
        "trigger": conditional["condition_for_execution"], "max_additional_outputs": 4,
        "analysis_label": conditional["analysis_label"], "independent_new_source": False, "jobs": jobs})
    artifacts["preparation_manifest.json"] = encoded({
        "status": "prepared_only_not_queued", "execution_authority": "Root agent must separately evaluate the registered trigger; this factory never queues or uploads.",
        "conditional_plan_sha256": sha(conditional_bytes), "source_metadata_sha256": sha(metadata_bytes),
        "primary_graphs": bases, "edit_instruction": NEW_EDIT, "explicit_event_addition": addition,
        "static_checks": checks, "graph_sha256": {name: sha(data) for name, data in artifacts.items() if name != "controls.json"},
        "inference_backend": "Existing service native PyTorch SDPA with Triton enabled; same model wiring as primary graphs.",
        "limitations": ["These are same-source, same-noise exploratory controls, not independent new samples.",
                        "No generated output or mechanism claim exists merely because preparation passed."]})
    return artifacts


def save_prepared(directory, artifacts):
    directory = Path(directory)
    # Check all collisions before writing anything; never overwrite different bytes.
    for name, data in artifacts.items():
        path = directory / name
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError("refusing to overwrite different prepared artifact: " + str(path))
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    for name, data in artifacts.items():
        path = directory / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
            created.append(name)
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    artifacts = prepare(args.root)
    created = [] if args.check_only else save_prepared(args.root / "configs/prepared_controls", artifacts)
    print(json.dumps({"status": "prepared_only_not_queued", "graphs": 4, "static_checks_passed": True,
                      "created": created, "check_only": args.check_only}, ensure_ascii=False))


if __name__ == "__main__":
    main()
