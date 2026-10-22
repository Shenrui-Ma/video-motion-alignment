"""Display signed offsets and rank schedules on the same seven delayed tasks."""
from statistics import mean

SCHEDULES = ("early", "fixed", "late", "split", "global_weak")
DELAYED = {"short_0252", "05_real_megumi_v", "short_0358", "long_0039",
           "long_0059", "musk05", "sam07"}
SUMMARIES = {
    "short_0252": "早期、中期、分段和全程弱引导都已接近参考动作时间；后期引导仍明显延后。",
    "05_real_megumi_v": "早期、分段和全程弱引导的手臂动作已对齐，中期也接近参考；后期仍延后。",
    "short_0358": "全程弱引导的时间偏移最小。早期与分段引导改变了构图和旁边人物的姿态。",
    "long_0039": "早期与全程弱引导对齐了已检查的动作；分段和中期部分改善，后期仍有明显延后。",
    "long_0059": "全程弱引导与分段引导明显改善收回手的延后；早期部分改善，中期与后期保留了原有延后。",
    "short_0085": "普通编辑原本已近同步，各引导版本保留了主要动作。本例只做动作保持检查，未测具体偏移帧数。",
    "short_0274": "普通编辑原本已近同步，各引导版本保留了主要动作。本例只做动作保持检查，未测具体偏移帧数。",
    "musk05": "早期与全程弱引导接近参考，分段略提前；中期仍延后，后期偏移加大。",
    "firefly06": "各引导版本都补回了短暂上脸手势，手的位置、朝向与形状仍有差异。",
    "sam07": "早期、中期、分段与全程弱引导接近参考；后期保留了普通编辑的延后。",
}


def event_offset(case, event, role):
    if event.get("measurement_kind") == "previously_reviewed_broad_phase_interval":
        return None
    source = event.get("source")
    # This case's frozen 39–44 is a search window; compare stable poses to stable poses.
    if case["source_id"] == "firefly06" and event["id"] == "early_eye_insert":
        source = [41, 42]
    if role == "source":
        return 0.0 if isinstance(source, list) else None
    if role in ("native", "fixed"):
        value = event.get(role)
    else:
        review = case["arms"][role].get("review") or {}
        found = next((e for e in review.get("events", []) if e["id"] == event["id"]), {})
        value = found.get(role)
    if not isinstance(source, list) or not isinstance(value, list):
        return None
    return mean(value) - mean(source)


def arm_lag(case, role):
    if role == "source":
        return 0.0
    review = (case["arms"][role].get("review") if role in case["arms"] else
              next((a["review"] for a in case["arms"].values() if a.get("review")), None))
    windows = ((review or {}).get("historical_window_diagnostics") or {}).get("windows", [])
    value = (windows[0].get(role) or {}).get("0.3") if windows else None
    return value


def add_display_metrics(data, source_scores, historical_verdicts):
    roles = data["roles"]
    for case in data["cases"]:
        sid = case["source_id"]
        case["source_MF"] = source_scores["cases"][sid]["score"]
        for role in ("native", "fixed"):
            if case["control_verdicts"][role] == "历史已审阅":
                case["control_verdicts"][role] = historical_verdicts["cases"][sid][role]["verdict"]
        case["event_offsets"] = {
            e["id"]: {r: event_offset(case, e, r) for r in roles}
            for e in case["events"]
        }
        case["arm_offsets"] = {r: arm_lag(case, r) for r in roles} if not case["events"] else {}
        case["mean_absolute_offset"] = {}
        for role in roles:
            values = ([case["arm_offsets"][role]] if not case["events"] else
                      [case["event_offsets"][e["id"]][role] for e in case["events"]])
            case["mean_absolute_offset"][role] = (
                mean(abs(v) for v in values) if values and all(v is not None for v in values) else None
            )
        case["display_summary"] = SUMMARIES[sid]
    selected = [c for c in data["cases"] if c["source_id"] in DELAYED]
    assert len(selected) == 7
    rows = []
    for role in SCHEDULES:
        values = [c["mean_absolute_offset"][role] for c in selected]
        assert all(v is not None for v in values)
        passed = sum((c["control_verdicts"][role] if role == "fixed" else
                      c["arms"][role]["review"]["task_verdict"]) == "PASS_CORE_EDIT" for c in data["cases"])
        rows.append(dict(role=role, mean_absolute_frames=mean(values),
                         task_count=len(selected), edit_passed=passed, edit_total=len(data["cases"])))
    rows.sort(key=lambda r: r["mean_absolute_frames"])
    data["ranking"] = dict(rows=rows, source_ids=[c["source_id"] for c in selected],
                           native_mean_absolute_frames=mean(c["mean_absolute_offset"]["native"] for c in selected),
                           aggregation="Mean absolute offset within each task, then equal-weight task mean; Sam05 uses frozen arm lag.")
    return data["ranking"]
