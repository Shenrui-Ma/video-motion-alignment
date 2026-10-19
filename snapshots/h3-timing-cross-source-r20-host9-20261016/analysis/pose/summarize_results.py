"""Compact frozen evaluator outputs; do not infer lag where evaluator says UNKNOWN."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'analysis/pose'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for p in sorted((OUT/'pilot').glob('*.timing.json')):
 d=json.loads(p.read_text())
 for r in d['diagnostics']:
  rows.append({'file':p.name,'file_sha256':sha(p),'confidence':d['confidence_threshold'],'window':r['window'],'feature':r['feature'],'status':r['status'],'flags':r.get('flags'),'reliable_lag_frames':r.get('reliable_lag_frames'),'best':r.get('best'),'unqualified_best':r.get('unqualified_best'),'same_frame':r.get('same_frame')})
if len(rows)!=60:raise ValueError(f'Expected 2 arms x2 confidence x3 windows x5features=60, got {len(rows)}')
gate=json.loads((OUT/'remote_evidence/audit/completed_pair_gate.json').read_text())
common=[]
for p in sorted((OUT/'common_support').glob('threshold*.json')):
 d=json.loads(p.read_text())
 for r in d['results']:
  common.append({'confidence':d['confidence_threshold'],**r})
result={'timing':rows,'common_support':common,'execution':gate,'limitations':['Previously viewed development case, not an unseen test set.','UNKNOWN is retained; lower lag without coverage/shape is not success.','Pose timing is separate from ghosting, identity, background, and full motion quality.']}
(OUT/'compact_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in rows:
 if r['feature'] in ('arm_direction','wrist_relative','left_arm_direction','right_arm_direction'):
  print(r['file'],r['window'],r['feature'],r['reliable_lag_frames'],r['status'],r['flags'])
