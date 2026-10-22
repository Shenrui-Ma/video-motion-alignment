"""Wait after a newly encoded Native video for a bound visual task review."""
import json
import time


def validate_review(review, request):
    for field in ("source_id", "run_id", "native_gate_sha256",
                  "video_sha256", "producer_seal_sha256"):
        if review.get(field) != request[field]:
            raise ValueError("Native visual review binding differs: " + field)
    if review.get("schema") != "r150-native-visual-review-v1":
        raise ValueError("Native visual review schema differs")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("Native visual reviewer required")
    if review.get("passed") is not True or review.get("task_completed") is not True:
        raise ValueError("Native visual review rejected the base editing task")


def wait_native_review(root, run_id, owner, state, timeout=600):
    import service
    from r132_contract import read, sha, require

    contract = read(root / "configs/scientific_contract.json")
    spec = next(row for row in contract["cases"] if row["run_id"] == run_id)
    if spec["arm"] != "native":
        return
    require(contract["condition_recovery"]["requires_shared_cache_native"],
            "Native review expected only for newly shared cached conditions")
    gate_path = root / "analysis/postrun" / spec["source_id"] / (run_id + "_GATE.json")
    gate = read(gate_path)
    require(gate["passed"] and gate["role"] == "native" and
            gate["service_owner"] == owner, "Native runtime gate is incomplete")
    request = {
        "schema": "r150-native-visual-review-request-v1",
        "source_id": spec["source_id"], "run_id": run_id,
        "native_gate_sha256": sha(gate_path),
        "video_sha256": gate["video"]["sha256"],
        "producer_seal_sha256": sha(root / "deploy_manifest.json"),
        "video": gate["video"]["file"],
        "native_gate": str(gate_path),
        "review_file": str(root / "audit/NATIVE_VISUAL_REVIEW.json"),
        "scope": "Check requested identity/appearance and preservation of the required scene.",
        "created_unix": time.time(), "timeout_seconds": timeout,
    }
    service.write_json(root / "audit/NATIVE_VISUAL_REVIEW_REQUEST.json", request)
    state(status="waiting_native_visual_review", current=None, completed=[run_id])
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        service.assert_owned(owner)
        review_path = root / "audit/NATIVE_VISUAL_REVIEW.json"
        if review_path.exists():
            review = json.loads(review_path.read_text())
            validate_review(review, request)
            service.write_json(root / "audit/NATIVE_VISUAL_REVIEW_RELEASE.json", {
                "passed": True, "request_sha256": sha(root / "audit/NATIVE_VISUAL_REVIEW_REQUEST.json"),
                "review_sha256": sha(review_path), "run_id": run_id,
                "wait_seconds": time.monotonic() - started,
                "created_unix": time.time(),
            })
            return
        time.sleep(5)
    raise TimeoutError("Native visual review not received within 600 seconds")
