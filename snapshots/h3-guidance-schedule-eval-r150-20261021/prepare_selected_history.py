"""Bind the five selected historical controls while actual producers are pending."""
import copy
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, bound, read, require, verify_record, write


def main():
    selection = read(ROOT / "SELECTED_TASKS.json")
    inventory_path = ROOT.with_name(
        "h3-guidance-schedule-eval-r149-20261020"
    ) / "extension/candidate_inventory.json"
    inventory = read(inventory_path)
    events_path = ROOT / "EVALUATION_EVENTS.json"
    events = {c["candidate_id"]: c for c in read(events_path)["cases"]}
    ids = ["r89_short_0085", "r89_short_0274", "musk05", "firefly06", "sam07"]
    records = []
    for task_id in ids:
        source = next(c for c in inventory["candidates"] if c["candidate_id"] == task_id)
        item = copy.deepcopy(source)
        for role, media in item["media"].items():
            if media is not None:
                verify_record(media)
        if "prompt_sha256" in item:
            require(
                hashlib.sha256(item["prompt"].encode()).hexdigest() == item["prompt_sha256"],
                "Historical prompt changed: " + task_id,
            )
        event_record = events[task_id]
        require(event_record["valid_frames"] == item["valid_frames"], "Frame domain differs")
        for event in event_record["events"]:
            for field in ("source_interval_inclusive", "native_interval_inclusive"):
                interval = event.get(field)
                if interval is not None:
                    require(
                        len(interval) == 2 and 0 <= interval[0] <= interval[1] < item["valid_frames"],
                        "Historical event outside valid domain",
                    )
            require(all(v is None for v in event["new_outputs"].values()), "New result in event freeze")
        for evidence in event_record["evidence"]:
            verify_record(evidence)
        item["evaluation_task_id"] = task_id
        item["actual_new_producer_binding"] = None
        item["new_output_status"] = "AWAITING_ACTUAL_PRODUCER_CONTRACT"
        item["frozen_events"] = event_record
        item["root_selection"] = {
            "record": bound(ROOT / "SELECTED_TASKS.json"),
            "approved": True,
            "overrides_older_candidate_selection_status": True,
        }
        item["required_new_roles"] = (
            ["early", "late", "split", "global_weak"] if task_id.startswith("r89_")
            else ["fixed", "early", "late", "split", "global_weak"]
        )
        item["fixed_role_rule"] = (
            "Exact historical same-bin 7–15 control is reused"
            if task_id.startswith("r89_")
            else "Await new same-bin 7–15 output; legacy_weight3 remains a separate historical role"
        )
        path = ROOT / "selected_history" / f"{task_id}.json"
        if path.exists():
            require(read(path) == item, "Historical record changed; archive before amendment")
        else:
            write(path, item)
        records.append(bound(path))
    write(ROOT / "audit/SELECTED_HISTORY_PREPARATION.json", {
        "schema": "r150-selected-history-preparation-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "inventory": bound(inventory_path),
        "events": bound(events_path),
        "records": records,
        "new_outputs_required_in_these_five_tasks": 23,
        "new_generated_outputs_observed": 0,
        "media_copied": False,
        "GPU_started": False,
    })
    print("Bound five selected historical controls; no new result or runtime fabricated.")


if __name__ == "__main__":
    main()
