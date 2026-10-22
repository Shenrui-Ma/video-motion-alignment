"""Prepare a CPU request only after a new Sam arm has passed media intake."""
import argparse
from pathlib import Path
import shlex
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import read, bound, verify_record, require, write

p = argparse.ArgumentParser()
p.add_argument("--schedule", required=True, choices=("early", "late", "split", "global_weak"))
a = p.parse_args()
old = ROOT.parent / "h3-timing-phase-combined-eval-r148-20261020/sam_final_pose"
plan = read(ROOT / "sam_final_pose/PLAN.json")
verify_record(plan["historical_plan"])
pres = read(ROOT / "review/05_real_megumi_v" / a.schedule / "PRESENTATION.json")
require(pres["schedule"] == a.schedule and pres["valid_frames"] == 141, "Unexpected presentation")
verify_record(pres["new_video"])
folder = ROOT / "sam_final_pose" / a.schedule
require(not (folder / "REQUEST.json").exists(), "Preserve existing request")
folder.mkdir(exist_ok=True)
remote = Path("/data4/researcher/h3_runs/guidance_schedule_evaluation_r149_20261020/sam_final_pose") / a.schedule
request = read(old / "REQUEST.json")
request.update(video={"file": str(remote / "video.mp4"), "sha256": pres["new_video"]["sha256"]},
               gate=pres["validated_execution"]["gate"], output_dir=str(remote),
               plan=bound(ROOT / "sam_final_pose/PLAN.json"))
write(folder / "REQUEST.json", request)
shutil.copy2(old / "extract_final_cpu.py", folder / "extract_final_cpu.py")
(folder / "RUN_AFTER_UPLOAD.txt").write_text(
    "CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python " +
    shlex.quote(str(remote / "extract_final_cpu.py")) + "\n")
print(folder)
