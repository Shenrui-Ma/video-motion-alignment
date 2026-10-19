"""Frozen files only; no external observer or process transport."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL_SHA='9ae36083faa544b532da6939a78115aec62de8be346e4b07ca4c3989f7945b99'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def case_for(run):
    from r41_contract import RUN_ID,SEED
    require(run==RUN_ID,'unregistered static run');return {'seed':SEED}
def bindings():
    require(sha(ROOT/'PROTOCOL.json')==PROTOCOL_SHA,'scientific protocol changed')
    for name,digest in read_json(ROOT/'configs/evidence_hashes.json').items():require(sha(ROOT/name)==digest,'parent evidence changed '+name)
    return {'comfy':'/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI'}

def inside(path,root):
    p=Path(path);r=Path(root).resolve()
    require(p.is_absolute() and not p.is_symlink() and p.resolve().is_relative_to(r),'archive path escape')
    return p
