"""Attach only pre-existing, exact-hash data; no network or model load."""
import hashlib,json,os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=read(R/"SEAL.json")["files"]
for rel,source in read(R/"audit/REMOTE_REUSE_PLAN.json").items():
 p,s=R/rel,Path(source)
 assert s.exists(),str(s)
 if rel=="runtime/ive":
  assert s.is_dir()
 else:
  assert s.is_file() and sha(s)==seal[rel],str(s)
 p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.symlink_to(s,target_is_directory=s.is_dir())
 if rel=="runtime/ive":
  assert p.resolve()==s.resolve()
 else:assert sha(p)==seal[rel]
print("Existing runtime/media hashes verified; no model loaded.")
