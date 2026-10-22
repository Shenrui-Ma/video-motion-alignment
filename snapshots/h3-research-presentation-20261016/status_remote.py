import subprocess,json,datetime
code = r"""
from pathlib import Path
import json
for name in ["timing_pose_feedback_r19_20261016", "timing_cross_source_r20_20261016"]:
 p=Path("/data5/researcher/h3_runs")/name
 print(name)
 print((p/"logs/controller_state.json").read_text())
 for f in (p/"audit").glob("**/*.json"):
  if f.name.startswith("r19_s05") and "observer" in str(f.parent):
   d=json.loads(f.read_text()); print(str(f.relative_to(p)),str({k:v for k,v in d.items() if k in ["status","error","completed_forward_calls","completed_updates","decisions","full_indices","total_nfe","chosen_callbacks"]})[-5000:])
 print("logtail", "\n".join((p/"logs/comfyui.log").read_text(errors="replace").splitlines()[-5:]))
"""
r=subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","H3_SERVER_A","python3 -"],input=code,text=True,capture_output=True)
print(datetime.datetime.now(datetime.timezone.utc).isoformat());print(r.stdout);print(r.stderr)
