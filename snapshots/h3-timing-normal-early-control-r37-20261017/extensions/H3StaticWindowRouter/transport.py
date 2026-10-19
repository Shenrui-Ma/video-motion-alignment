"""Frozen files only; no external observer or process transport."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL_SHA='7a54ab45db4343f66007d334e14e3b7a0eb571227a8fc7e6b8af6de0ce1fea8a'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def case_for(run):
    from r37_contract import RUN_ID,SEED
    require(run==RUN_ID,'unregistered static run');return {'seed':SEED}
def bindings():
    require(sha(ROOT/'PROTOCOL.json')==PROTOCOL_SHA,'scientific protocol changed')
    for name,digest in read_json(ROOT/'configs/evidence_hashes.json').items():require(sha(ROOT/name)==digest,'parent evidence changed '+name)
    return {'comfy':'/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI'}

def inside(path,root):
    p=Path(path);r=Path(root).resolve()
    require(p.is_absolute() and not p.is_symlink() and p.resolve().is_relative_to(r),'archive path escape')
    return p
