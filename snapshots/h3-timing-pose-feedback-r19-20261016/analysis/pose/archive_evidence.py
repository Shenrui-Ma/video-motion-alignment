"""Package completed read-only R19 evidence into this evaluator-owned analysis dir."""
from pathlib import Path
import hashlib,json,tarfile,time
ROOT=Path('/data5/researcher/h3_runs/timing_pose_feedback_r19_20261016')
RUN='r19_s05_pose_observer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=ROOT/'analysis/pose/replication';out.mkdir(parents=True,exist_ok=True)
    gate=json.loads((out/(RUN+'_integrity.json')).read_text());assert gate['passed']
    files=[]
    for folder in ['audit/observations','processes']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.json','.log'))
    for name in [f'audit/counterfactual/{RUN}.json',f'audit/{RUN}_conditioning.json',f'audit/{RUN}_noise.json',f'audit/x0/{RUN}/manifest.json',f'logs/{RUN}_history.json','logs/controller_state.json','configs/admission.json','configs/runtime_provenance.json','deploy_manifest_v1.json','audit/r20_parallel_admission_update.json']:
        p=ROOT/name
        if p.is_file():files.append(p)
    files=sorted(set(files))
    record={'created_unix':time.time(),'files':{str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files},'remote_root':str(ROOT),'large_tensors':'Retained remotely with actual loaded finite/signature checks in independent integrity JSON. Raw final MP4 separately downloaded.'}
    m=out/'complete_evidence_manifest.json'
    with m.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    bundle=out/'complete_evidence.tar.gz'
    with tarfile.open(bundle,'x:gz') as t:
        for p in files:t.add(p,arcname=str(p.relative_to(ROOT)))
        t.add(m,arcname='complete_evidence_manifest.json')
    assert all(sha(ROOT/n)==r['sha256'] for n,r in record['files'].items())
    print(json.dumps({'bundle':str(bundle),'sha256':sha(bundle),'files':len(files),'bytes':bundle.stat().st_size}))
if __name__=='__main__':main()
