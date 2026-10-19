"""Lossless compact view of completed frozen evaluations; UNKNOWN is never filled."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
FEATURES=('arm_direction','wrist_relative','left_arm_direction','right_arm_direction')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];runs={};pairs={};common=[]
for arc in sorted((HERE/'captured').glob('*')):
 if not (arc/'CPU_COMPLETE.json').exists():continue
 done=read(arc/'CPU_COMPLETE.json');gate=read(arc/'RUN_GATE.json')
 runs[arc.name]={'complete':done,'execution':gate,'local_playback_verified':read(arc/'PLAYBACK_GATE.json')['passed'] if (arc/'PLAYBACK_GATE.json').exists() else False}
 for p in sorted((arc/'timing').glob('*/*.timing.json')):
  d=read(p)
  if len(d['diagnostics'])!=15 or any(len(x['curve'])!=49 for x in d['diagnostics']):raise ValueError('frozen curve inventory')
  for r in d['diagnostics']:
   rows.append({'run_id':arc.name,'case':gate['case']['case_id'],'seed':gate['seed'],'arm':gate['arm'],'file':str(p),'sha256':sha(p),'confidence':d['confidence_threshold'],'window':r['window'],'feature':r['feature'],'status':r['status'],'flags':r.get('flags'),'reliable_lag_frames':r.get('reliable_lag_frames'),'best':r.get('best'),'unqualified_best':r.get('unqualified_best'),'same_frame':r.get('same_frame')})
for d in sorted((HERE/'pairs').glob('*')):
 if not(d/'PAIR_COMPLETE.json').exists():continue
 pairs[d.name]=read(d/'PAIR_COMPLETE.json')
 for p in sorted(d.glob('common_support_*.json')):
  data=read(p)
  for r in data['results']:common.append({'pair':d.name,'file_sha256':sha(p),'confidence':data['confidence_threshold'],**r})
result={'runs':runs,'pairs':pairs,'timing':rows,'common_support':common,'limitations':['Eight preselected jobs; all completed results retained including normal, worse and UNKNOWN.','Windows were selected from source only before generation. Two sources and two seeds are not a broad benchmark.','Confidence thresholds and frozen timing rejection unchanged.','Source-only .5 wrist support in both primary windows is insufficient; report pair actual support and retain UNKNOWN.','No cleanup or architecture novelty conclusion from this consumer.','Positive lag means edited action is later than reference under the frozen correspondence convention.']}
(HERE/'COMPACT_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['R24 completed results only. UNKNOWN retained. Positive lag: edited motion later.']
for r in rows:
 if r['feature'] in FEATURES:
  lines.append(f'{r["run_id"]} conf={r["confidence"]} window={r["window"]} {r["feature"]}: lag={r["reliable_lag_frames"]} status={r["status"]} flags={r["flags"]}')
(HERE/'COMPACT_TIMING.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'completed_runs':len(runs),'pairs':len(pairs),'timing_rows':len(rows),'common_rows':len(common)}))
