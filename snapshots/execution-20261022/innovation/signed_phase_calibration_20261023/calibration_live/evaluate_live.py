"""Offline diagnostics of a new, complete observed trajectory.

This entry point never modifies or substitutes the historical replay gate.
The probability equations are shared with the frozen historical analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "frozen_probability_analysis", ROOT.parent / "calibration/evaluate_probabilities.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_events(annotations, plan, plan_sha):
    if annotations.get("schema") != "h3-live-phase-event-annotations-v1":
        raise ValueError("new live-video annotations required")
    if annotations.get("plan_sha256") != plan_sha or annotations.get("case_id") != plan["case_id"]:
        raise ValueError("annotation plan/case differs")
    provenance = annotations["video_provenance"]
    if provenance["source"]["sha256"] != plan["source_video_provenance"]["sha256"]:
        raise ValueError("frozen source video differs")
    for method in plan["methods"]:
        item = provenance[method]
        if (not valid_sha(item["sha256"]) or not item.get("trajectory_id")
                or item.get("annotation_source") != "new_complete_video"
                or not valid_sha(item.get("annotation_record_sha256"))
                or type(item.get("frame_count")) is not int or item["frame_count"] <= 0):
            raise ValueError("complete new-video annotation provenance required")
    events = annotations["events"]
    if [e["id"] for e in events] != [e["id"] for e in plan["events"]]:
        raise ValueError("frozen event set/order differs")
    for event, frozen in zip(events, plan["events"]):
        if event["source"] != frozen["source_interval_frames"]:
            raise ValueError("frozen source event interval differs")
        for method in plan["methods"]:
            obs = event[method]
            if obs.get("status") == "observed":
                interval = obs.get("interval")
                if (not isinstance(interval, list) or len(interval) != 2
                        or any(type(v) is not int for v in interval)
                        or not 0 <= interval[0] <= interval[1] < provenance[method]["frame_count"]):
                    raise ValueError("invalid new-video event interval")
            elif obs.get("status") in ("not_visible", "not_identifiable"):
                if obs.get("interval") is not None or not obs.get("reason"):
                    raise ValueError("missing events require an explicit reason and no interval")
            else:
                raise ValueError("unreviewed event")


def validate_gate(capture, capture_sha, gate, annotations, method, contract):
    sigmas = contract.get("sample_sigmas_video", [])
    if (not valid_sha(contract.get("science_contract_sha256"))
            or not valid_sha(contract.get("noise_sha256"))
            or len(sigmas) != 21 or not np.isfinite(sigmas).all()):
        raise ValueError("complete frozen scientific contract required")
    if gate.get("schema") != "h3-live-phase-trajectory-gate-v1" or gate.get("passed") is not True:
        raise ValueError("successful complete live trajectory gate required")
    if (gate.get("case") != annotations["case_id"] or gate.get("method") != method
            or gate.get("science_contract_sha256") != contract["science_contract_sha256"]):
        raise ValueError("trajectory science/case/method differs")
    for field, value in (("callback_count", 20), ("actual_model_forward_count", 20),
                         ("completed_blocks", 1000), ("extra_model_forward_calls", 0)):
        if type(gate.get(field)) is not int or gate[field] != value:
            raise ValueError("incomplete or extra model execution")
    video = annotations["video_provenance"][method]
    if (gate.get("trajectory_id") != video["trajectory_id"]
            or gate.get("actual_video_sha256") != video["sha256"]
            or not valid_sha(gate.get("observation_manifest_sha256"))):
        raise ValueError("annotations and capture trajectory differ")
    items = gate["captures"]
    if (len(items) != 2 or sorted(i["step_zero_based"] for i in items) != [9, 19]
            or len({i["qk_sha256"] for i in items}) != 2):
        raise ValueError("exactly two frozen observations required")
    for item in items:
        identity = item["forward_identity"]
        expected = {"case": gate["case"], "method": method,
                    "trajectory_id": gate["trajectory_id"],
                    "science_contract_sha256": contract["science_contract_sha256"],
                    "layer_zero_based": 25, "step_zero_based": item["step_zero_based"],
                    "state_file_sha256": item["state_file_sha256"],
                    "sample_sigmas_video": contract["sample_sigmas_video"],
                    "noise_sha256": contract["noise_sha256"]}
        if any(identity.get(k) != v for k, v in expected.items()):
            raise ValueError("capture belongs to a different state, method or science contract")
        if (item.get("layer_zero_based") != 25 or not valid_sha(item["qk_sha256"])
                or not valid_sha(item["state_file_sha256"])):
            raise ValueError("invalid observation identity")
        for field in ("packed_x", "raw_packed_x0"):
            tensor = identity.get(field, {})
            if (tensor.get("finite") is not True or tensor.get("dtype") != "torch.float32"
                    or not valid_sha(tensor.get("sha256")) or not tensor.get("shape")):
                raise ValueError("missing actual forward input/output identity")
    chosen = next((i for i in items if i["qk_sha256"] == capture_sha), None)
    if chosen is None or capture.get("forward_identity") != chosen["forward_identity"]:
        raise ValueError("actual capture byte/state identity differs")
    for key in ("case", "method", "step_zero_based", "layer_zero_based"):
        if capture.get(key) != chosen["forward_identity"][key]:
            raise ValueError("capture metadata differs")
    if capture.get("schema") != "h3-passive-qk-capture-v1":
        raise ValueError("unexpected capture schema")


def summarize_live(p, rp, spans, valid, annotations, method):
    observed, missing = [], {}
    for event in annotations["events"]:
        obs = event[method]
        if obs["status"] != "observed":
            missing[event["id"]] = {"event_id": event["id"], "status": obs["status"],
                                     "reason": obs["reason"], "reference_interval": event["source"]}
            continue
        lo, hi = obs["interval"]
        slo, shi = event["source"]
        observed.append({"id": event["id"], "source": event["source"], method: [lo, hi],
                         "midpoint_offsets_frames": {method: (lo + hi - slo - shi) / 2},
                         "offset_uncertainty_frames": {method: [lo - shi, hi - slo]}})
    result = base.summarize(p, rp, spans, valid,
                            {"case_id": annotations["case_id"], "frozen_events": observed}, method)
    by_id = {e["event_id"]: e for e in result["events"]} | missing
    result["events"] = [by_id[e["id"]] for e in annotations["events"]]
    result["expected_event_count"] = len(annotations["events"])
    result["measured_event_count"] = sum(e["status"] == "measured_sparse_retrieval" for e in result["events"])
    result["all_events_measured"] = result["measured_event_count"] == result["expected_event_count"]
    result["event_selected_rows_descriptive_only"] = True
    result["semantic_phase_validated"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("capture", "trajectory-gate", "annotations", "contract", "numerical-check", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--method", choices=("native", "global_weak"), required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    import torch
    capture_bytes = args.capture.read_bytes()
    capture_sha = sha(capture_bytes)
    capture = torch.load(args.capture, map_location="cpu", weights_only=True)
    plan_bytes = (ROOT / "PLAN.json").read_bytes()
    annotations_bytes = args.annotations.read_bytes()
    annotations = json.loads(annotations_bytes)
    contract = json.loads(args.contract.read_bytes())
    gate_bytes = args.trajectory_gate.read_bytes()
    validate_events(annotations, json.loads(plan_bytes), sha(plan_bytes))
    validate_gate(capture, capture_sha, json.loads(gate_bytes), annotations, args.method, contract)
    numerical_bytes = args.numerical_check.read_bytes()
    numerical = json.loads(numerical_bytes)
    if (numerical.get("capture_sha256") != capture_sha
            or numerical.get("policy_sha256") != contract["numerical_policy_sha256"]
            or numerical.get("numerical_definition_pass") is not True):
        raise ValueError("same capture numerical definition must pass the frozen policy")
    def array(key):
        value = capture[key]
        return value.detach().float().numpy() if isinstance(value, torch.Tensor) else np.asarray(value)
    raw = {k: array(k) for k in ("raw_Q_C", "raw_Q_R", "raw_K_R")}
    if any(x.ndim != 4 or x.shape[1:] != (8, 56, 128) for x in raw.values()):
        raise ValueError("all frozen probes and heads required")
    q = base.normalized_content(raw["raw_Q_C"], array("q_norm_weight"), capture["q_norm_eps"])
    qr = base.normalized_content(raw["raw_Q_R"], array("q_norm_weight"), capture["q_norm_eps"])
    k = base.normalized_content(raw["raw_K_R"], array("k_norm_weight"), capture["k_norm_eps"])
    valid = np.asarray(capture["valid_bins"], dtype=bool)
    spans = array("physical_frame_spans_inclusive")
    p, rp = base.retrieval_probabilities(q, k, valid), base.retrieval_probabilities(qr, k, valid)
    result = summarize_live(p, rp, spans, valid, annotations, args.method)
    result.update(capture_sha256=capture_sha, trajectory_gate_sha256=sha(gate_bytes),
                  event_manifest_sha256=sha(annotations_bytes), plan_sha256=sha(plan_bytes),
                  numerical_check_sha256=sha(numerical_bytes),
                  science_contract_sha256=contract["science_contract_sha256"],
                  step_zero_based=capture["step_zero_based"], layer_zero_based=25,
                  actual_video_sha256=annotations["video_provenance"][args.method]["sha256"],
                  numerical_definition="FP32 RMS; FP64 sparse logits/LSE/softmax; all heads and probes",
                  alpha_control_deployed=False)
    args.output.mkdir()
    np.savez_compressed(args.output / "probabilities.npz", canvas=p, reference=rp,
                        valid_bins=valid, physical_frame_spans_inclusive=spans,
                        spatial_ids=np.asarray(capture["spatial_ids"]))
    (args.output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"method": args.method, "step": capture["step_zero_based"],
                      "measured": result["measured_event_count"], "expected": result["expected_event_count"]}))


if __name__ == "__main__":
    main()
