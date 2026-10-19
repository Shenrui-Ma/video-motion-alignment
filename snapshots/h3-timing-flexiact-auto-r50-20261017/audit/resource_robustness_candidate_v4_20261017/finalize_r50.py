from pathlib import Path
import json,hashlib,subprocess,time
C=Path(__file__).resolve().parent
snap=json.loads((C/'SOURCE_SNAPSHOTS.json').read_text());records={}
for rel,row in snap['r50']['files'].items():
 a=C/'r50/before'/rel;b=C/'r50/overlay'/rel
 row['after_sha256']=hashlib.sha256(b.read_bytes()).hexdigest()
 row['live_before_sha_matches']=hashlib.sha256((Path(snap['r50']['source_root'])/rel).read_bytes()).hexdigest()==row['before_sha256']
 records[rel]=row
(C/'SOURCE_SNAPSHOTS.json').write_text(json.dumps(snap,indent=2)+'\n')
logs=[]
for name in ['test_resource_v4.py','test_supervision_regression.py']:
 r=subprocess.run(['python3',str(C/'tests'/name)],text=True,capture_output=True)
 log=C/(name+'.log');log.write_text(r.stdout+r.stderr);logs.append({'test':name,'returncode':r.returncode,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
 if r.returncode:raise SystemExit(r.stderr)
files={str(p.relative_to(C/'r50/overlay')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (C/'r50/overlay').rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
ready={'status':'CPU_VERIFIED_CANDIDATE','written_unix':time.time(),'tests':44,'test_runs':logs,'producer_unchanged':all(v['live_before_sha_matches'] for v in records.values()),'files':files,'patch_sha256':hashlib.sha256((C/'r50/candidate.patch').read_bytes()).hexdigest(),'GPU_executed':False}
(C/'R50_READY.json').write_text(json.dumps(ready,indent=2)+'\n')
print(json.dumps(ready,indent=2))
