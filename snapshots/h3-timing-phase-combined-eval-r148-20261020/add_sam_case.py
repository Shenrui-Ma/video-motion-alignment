"""Append the exact historical Sam seed1311 comparison, preserving the four IVE cases."""
import argparse
import hashlib
import json
from pathlib import Path
from prepare_comparison import ROOT, bound, read, require, inspect, dimensions
from fractions import Fraction


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-id", required=True, help="Exact new producer source_id")
    p.add_argument("--run-id", required=True)
    p.add_argument("--producer-case", type=Path, required=True)
    p.add_argument("--noise-file-sha256", help="Actual historical .pt file SHA once producer verifies it")
    a = p.parse_args()
    legacy = ROOT.parent / "h3-timing-autoresearch-20261016"
    paths = {"source": legacy / "inputs/05_real_megumi_v.mp4",
             "native": legacy / "outputs/s05_full_seed1_native_x0_00001_.mp4",
             "fixed": legacy / "outputs/s05_full_seed1_mass_6to14_x0_00001_.mp4"}
    expected = {"source": "c80a126374966191cf87eebb8b8952d84fc88a7d6a56ca4c8be01a099ca2a857",
                "native": "7a65463d6cd54517851a1aa3bf3a3670d6bf07a28f0ca46e7b267e03799ec30b",
                "fixed": "8c7ffcf450fd6ecd7e3a5722765072e5798ede73c64b273e0ba7d960a93b2f9f"}
    media = {r: bound(path) for r, path in paths.items()}
    for role, item in media.items():
        require(item["sha256"] == expected[role], role + " legacy media changed")
        require(dimensions(inspect(item["file"])) == (1312, 736, 141, Fraction(24)), "Legacy geometry differs")
    ids = {"native": "s05_full_seed1_native_x0", "fixed": "s05_full_seed1_mass_6to14_x0"}
    runs = {}
    for role, rid in ids.items():
        graph_path = legacy / "configs" / (rid + ".json")
        graph = read(graph_path)
        runs[role] = {"run_id": rid, "graph": bound(graph_path), "router_node_50": graph["50"],
                      "history": bound(legacy / "logs" / (rid + "_history.json"))}
    fixed_graph = read(runs["fixed"]["graph"]["file"])
    prompt = fixed_graph["5"]["inputs"]["prompt"]
    require(read(runs["native"]["graph"]["file"])["5"]["inputs"]["prompt"] == prompt, "Legacy prompts differ")
    pair_path = legacy / "audit/s05_full_seed1_native_x0__s05_full_seed1_mass_6to14_x0_pair_check.json"
    require(read(pair_path)["passed"] is True, "Historical paired evidence failed")
    noise_path = legacy / "audit/s05_full_seed1_native_x0_noise.json"
    noise = read(noise_path)
    fixed_noise = read(legacy / "audit/s05_full_seed1_mass_6to14_x0_noise.json")
    require(noise["actual_noise_streams"] == fixed_noise["actual_noise_streams"], "Historical actual noise differs")
    round_path = legacy / "analysis/pose/ROUND_FINAL_REVIEW.json"
    historical = read(round_path)["runs"]
    diagnostic_runs = {}
    for role, rid in ids.items():
        diagnostic_runs[role] = next(r for r in historical.values() if r.get("video") == rid + "_00001_.mp4")
    windows = []
    for i, item in enumerate(diagnostic_runs["native"]["thresholds"]["0.3"]):
        w = {"window": item["window"], "fixed_phase": None}
        for role in ("native", "fixed"):
            w[role] = {threshold: diagnostic_runs[role]["thresholds"][threshold][i]["reliable_lag_frames"]
                       for threshold in ("0.3", "0.5")}
        windows.append(w)
    c = {"source_id": a.source_id, "title": "真人书记舞：替换为 Sam Altman",
         "dataset": "用户提供的历史真人舞蹈源片", "seed": 2026101311,
         "geometry": {"width": 1312, "height": 736, "sampled_frames": 141, "valid_frames": 141,
                      "fps": 24, "crop_xywh": [0, 0, 1312, 736]},
         "media": media, "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
         "prompt_source_label": "历史 Sam 人像参考＋真人舞蹈编辑的实际提交 prompt；非 IVEBench 官方指令。",
         "reference_image": bound(legacy / "inputs/sam_altman_village_global_20221117_original.jpg"),
         "historical_runs": runs, "historical_pair_gate": bound(pair_path),
         "historical_review": bound(legacy / "analysis/pose/pilot/EQUAL9_REVIEW.json"),
         "historical_full_review": bound(round_path),
         "historical_initial_noise": {"file": noise["cache_file"], "sha256": a.noise_file_sha256,
                                     "actual_tensor_signatures": noise["actual_noise_streams"],
                                     "receipt": bound(noise_path)},
         "events": [], "phases": [],
         "historical_window_diagnostics": {"record": bound(round_path), "feature": "arm_direction",
             "windows": windows, "note": "Existing offline pose lag windows, not human event boundary annotations. No denoising-time observer."},
         "official_MF": {"native": None, "fixed": None, "fixed_phase": None},
         "official_MF_status": "No completed official MF found for this exact seed1311/full141 trio; prepare source+Native+fixed+new tracking later.",
         "sampling_seconds": {"native": None, "fixed": None, "fixed_phase": None},
         "task_checks": ["真实成人替换外观与服装符合原参考意图", "原房间、镜头、边框、舞蹈动作序列保持",
                         "主窗50–65与三个后续评估窗分别记录；全141帧检查新增副作用"],
         "R148": {"status": "PENDING_NOT_GENERATED", "role": "fixed_phase", "run_id": a.run_id,
                  "producer_case": str(a.producer_case), "runtime_binding": str(ROOT / "runtime" / (a.source_id + ".json")),
                  "producer_seal": None, "completion": None}}
    path = ROOT / "EVALUATION_MANIFEST.json"
    m = read(path)
    require(len(m["cases"]) == 4 and all(x["source_id"] != a.source_id for x in m["cases"]), "Fifth case already exists")
    archive = ROOT / "history"
    archive.mkdir(exist_ok=True)
    (archive / ("EVALUATION_MANIFEST_four_" + bound(path)["sha256"] + ".json")).write_bytes(path.read_bytes())
    m["cases"].append(c)
    m["case_count"] = 5
    m["new_case_note"] = "Sam retains its original portrait reference, seed1311, frame window50..65 and complete141-frame media."
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(bound(path)))


if __name__ == "__main__":
    main()
