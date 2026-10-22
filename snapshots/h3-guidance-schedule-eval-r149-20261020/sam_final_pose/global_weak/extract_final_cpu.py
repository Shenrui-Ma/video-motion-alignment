"""One final-video CPU extraction with the original code and existing weights."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
request = json.loads((ROOT / "REQUEST.json").read_text())
assert str(ROOT) == request["output_dir"]
assert request["GPU"] is False and request["during_denoising"] is False
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(request["script"]) == request["script_sha256"]
for path, expected in request["weights_and_code"].items():
    assert Path(path).is_file() and sha(path) == expected, path
assert sha(request["video"]["file"]) == request["video"]["sha256"]
env = os.environ.copy()
env.update(CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1",
           OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4")
command = [sys.executable, request["script"], "--video", request["video"]["file"],
           "--output-dir", str(ROOT), "--aux-root", request["aux_root"],
           "--threads", "4", "--frame-start", "0", "--frame-end", "140", "--stride", "1"]
started = time.time()
with (ROOT / "extraction.log").open("xb") as log:
    subprocess.run(command, env=env, stdout=log, stderr=log, check=True)
pose = ROOT / (Path(request["video"]["file"]).stem + ".pose.json")
data = json.loads(pose.read_text())
assert data["video"]["sha256"] == request["video"]["sha256"]
assert [f["frame"] for f in data["frames"]] == list(range(141))
assert data["provenance"]["device"] == "cpu"
receipt = dict(passed=True, started_unix=started, finished_unix=time.time(),
               request_sha256=sha(ROOT / "REQUEST.json"), script_sha256=sha(__file__),
               pose=dict(file=str(pose), sha256=sha(pose), bytes=pose.stat().st_size),
               GPU_started=False, during_denoising=False, downloads=False,
               statistics=data["statistics"])
(ROOT / "EXTRACTION.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
