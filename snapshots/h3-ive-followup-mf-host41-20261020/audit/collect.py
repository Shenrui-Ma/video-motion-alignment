from pathlib import Path
import json,hashlib,subprocess,sys,math,time
R=Path(__file__).resolve().parents[1];REMOTE='/data4/researcher/h3_runs/ive_followup_mf_20261020'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def local(remote):
 p=Path(remote);return R/p.relative_to(REMOTE)
for folder in ['audit','state','results']:
 cmd=['rsync','-a','--exclude','collect.py','--exclude','__pycache__','H3_SERVER_B:'+REMOTE+'/'+folder+'/',str(R/folder)+'/'];p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stderr
verified=[]
for p in (R/'results').glob('*/*.json'):
 d=read(p);value=d.get('score',d.get('motion_fidelity'));assert isinstance(value,(int,float))and math.isfinite(value)
 m=read(R/'cases'/d['case']/'INPUTS.json');t=next(x for x in m['targets']if x['role']==d['role']);assert d['inventory_bindings']==t['inventory_bindings']and d['actual_generated_video_sha256']==t['full_sha256']
 for key in ['source_report','target_report']:
  f=local(d[key]['file']);assert sha(f)==d[key]['sha256'];r=read(f);assert r['passed'];track=f.parent/('tracks.pt'if d['benchmark']=='FlexiAct'else'tracks.npz');assert sha(track)==r['tracks_sha256']
 state=read(R/'state'/d['case']/(d['role']+'.json'));release=state['release'];rf=local(release['file']);assert sha(rf)==release['sha256'];rr=read(rf);assert rr['passed']and rr['CUDA_absent']and rr['process_absent']and rr['returncode']==0
 verified.append(dict(case=d['case'],role=d['role'],benchmark=d['benchmark'],score=value,inventory_bindings=d['inventory_bindings'],actual_generated_video_sha256=t['full_sha256'],source_score_sha256=m['source_score_sha256'],valid_frames=m['valid_frames'],evaluation_frames=m['evaluation_frames'],evaluation_fps=m['evaluation_fps'],result_file=str(p),result_sha256=sha(p),release_file=str(rf),release_sha256=sha(rf)))
p=R/'audit/RESULTS_VERIFIED.json';p.write_text(json.dumps(dict(created_unix=time.time(),completed_targets=len(verified),requested_targets=read(R/'configs/PLAN.json')['unique_targets'],results=verified),ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(completed=len(verified),file=str(p),sha256=sha(p))))
