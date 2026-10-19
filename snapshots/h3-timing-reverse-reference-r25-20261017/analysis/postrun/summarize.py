"""Compact all-outcome report; fixed metrics only, no re-selection."""
import hashlib,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def simple(rows):
 return [{k:r.get(k) for k in ('window','feature','status','flags','reliable_lag_frames')}|{'same_frame_error':r['same_frame']['error'],'same_frame_coverage':r['same_frame']['coverage'],'best_error':r['best']['error'] if r.get('best') else None} for r in rows]
def main():
 b=read(HERE/'BINDING.json');res={'created_unix':time.time(),'known_development_case':True,'source':'source05 Sam seed2026101311','runs':{},'quality_review':'pending independent fixed-frame visual review','limits':['Two arms on one selected development failure; not generalization.','Window and sampling schedule manually fixed, not automatic.','BLOCK removes target-video only; audio pathway remains.','SAME ideal algebra preserves target-video mass with audited numerical reconstruction tolerance.','Same-call unchanged target rows does not establish later hidden-state cause.','No wrong-time sparse control or claim of novelty.','UNKNOWN and low common support remain; bone metrics do not establish identity/edit/hand quality.']}
 for label,z in b['parents'].items():
  p=ROOT.parent/'h3-timing-spatial-r3-20261016/analysis/pose/pilot'
  res['runs'][label]={'old_frozen_baseline':True,'metrics':{str(c):simple(read(p/(z['run_id']+f'_00001_.threshold{c}.timing.json'))['diagnostics']) for c in (.3,.5)}}
 for lane,z in b['lanes'].items():
  arc=HERE/'captured'/z['run_id'];done=read(arc/'CPU_COMPLETE.json');gate=read(arc/'RUN_GATE.json')
  if not(done['passed'] and gate['passed'] and read(arc/'PLAYBACK_GATE.json')['passed']):raise ValueError('incomplete actual/output gate')
  res['runs'][lane]={'run_id':z['run_id'],'integrity_passed':True,'video':str(arc/'output'/Path(done['video']).name),'video_sha256':done['video_sha256'],'metrics':read(arc/'COMPACT_RESULTS.json'),'efficiency':gate['efficiency'],'NFE':gate['NFE'],'Euler_updates':gate['Euler_updates'],'actual_005_AV':gate['checks']['independent_actual_native005_AV'],'service_cleanup_claim':False}
 comp=HERE/'comparison';files=read(comp/'FILES.json')
 for name,h in files.items():
  if sha(comp/name)!=h:raise ValueError('common-support archive changed')
 res['common_support']={}
 for p in comp.glob('*.json'):
  if p.name in ('FILES.json','COMPARISON_COMPLETE.json'):continue
  d=read(p)
  res['common_support'][p.stem]=[{k:r[k] for k in ('window','feature','common_valid_fraction','status')}|{'errors':{name:x['same_frame_error_on_common_support'] for name,x in r['runs'].items()}} for r in d['results']]
 text=['R25 reverse-reference pilot: fixed-window development evaluation','', 'All comparisons use original physical times. The two new arms passed actual runtime/input/noise/prefix and final playback gates. Scientific interpretation remains separate from integrity.','', 'Primary50–65: direction(.3/.5), wrist(.3/.5); UNKNOWN is not zero.']
 for name,z in res['runs'].items():
  vals=[]
  for feat in ('arm_direction','wrist_relative'):
   for c in ('0.3','0.5'):
    rows=z['metrics'][c]
    if isinstance(rows,dict):vals.append(None);continue
    vals.append(next(r['reliable_lag_frames'] for r in rows if r['feature']==feat and r['window']==[50,65]))
  text.append(f'{name}: '+str(vals))
  if name.startswith('reverse_'):
   z['primary_four_lags']=vals;z['primary_complete_timing_gate']=all(v is not None and abs(v)<=2 for v in vals)
 text+=['','Four predeclared windows, both confidence thresholds:']
 for name,z in res['runs'].items():
  text.append(name)
  for c,rows in z['metrics'].items():
   if isinstance(rows,dict):text.append('  '+c+': UNKNOWN');continue
   for feat in ('arm_direction','wrist_relative'):
    rr=[r for r in rows if r['feature']==feat]
    text.append('  '+c+' '+feat+': '+str([(r['window'],r['reliable_lag_frames'],r['status'],r['flags']) for r in rr]))
 text+=['','All-four common support for arm direction (source intersection with Native, forwardFull, BLOCK and SAME):']
 for c in ('0.3','0.5'):
  key='native__full__reverse_block__reverse_same_'+c
  for row in res['common_support'].get(key,[]):
   if row['feature']=='arm_direction':text.append(c+' '+str(row))
 text+=['','Quality: fixed55/86/105 and42–82 clip review pending; do not treat numeric lag improvement as edit-quality success.','',*res['limits'],'','Efficiency recorded per arm in machine report; no speed diagnosis. Large original PT remain remote, local FILE_INVENTORY contains their exact path/SHA/size. Services are retained for root handoff; this report makes no cleanup claim.']
 (HERE/'FINAL_RESULTS.json').write_text(json.dumps(res,indent=2)+'\n');(HERE/'FINAL_RESULTS.txt').write_text('\n'.join(text)+'\n');print('\n'.join(text[:9]))
if __name__=='__main__':main()
