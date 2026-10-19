import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def audit_dir(value):
 p=Path(value).resolve()
 if p!=ROOT/'audit':raise ValueError('capacity audit root differs')
 return p
def validate_job(run_id):
 if run_id!='capacity_native_full_reserve8':raise ValueError('outside standalone capacity run')
 cfg=json.loads((ROOT/'configs/probe.json').read_text())
 if hashlib.sha256((ROOT/'configs/graph.json').read_bytes()).hexdigest()!=cfg['graph_sha256']:raise ValueError('capacity graph changed')
 return {'case':{'source_id':cfg['source_id']}}
