"""Claim newly prepared videos once, SHA-sync to .41, then arm AWQ evaluation."""
from pathlib import Path
import sys,json,subprocess,argparse,hashlib
D=Path(__file__).resolve().parent;Q=D.parent;sys.path.insert(0,str(Q));import sync_inputs as s
TARGET='/data4/research-user/h3_metrics_qwen_20261022/qwen_runtime/extension_live_incremental_20261023'
ready=set(['expand_short_0135_native', 'expand_short_0135_global_weak', 'expand_long_0161_native', 'expand_long_0161_global_weak', 'expand2_short_0166_native', 'expand2_short_0166_global_weak', 'expand2_short_0185_native', 'expand2_short_0185_global_weak', 'live_phase_short0358_native_20261023', 'live_phase_short0358_global_weak_20261023'])
discovered=set(json.loads((Q/'host60_extra/discovery_latest.json').read_text())['new_ready']);assert ready <= discovered
manifest=json.loads(s.remote(s.SOURCE_HOST,"from pathlib import Path;print(Path('/data/research-user/h3_metrics_20261022/code/manifest.json').read_text())"))
selected={**manifest,'jobs':[j for j in manifest['jobs'] if j['id'] in ready]}
assert len(selected['jobs'])==len(ready)==10
(D/'manifest.pending.json').write_text(json.dumps(selected,indent=2))
claim=r'''
from pathlib import Path
import json,sys,time,fcntl,hashlib,os
D=Path('/data3/research-user/h3_metrics_20261022/qwen_runtime/extra26_20261022');x=json.load(sys.stdin)
def alive(rec):
 try:
  p=Path('/proc')/str(rec['pid']);v=(p/'stat').read_text().rsplit(')',1)[1].split();return p.stat().st_uid==rec['uid'] and v[19]==str(rec['start_ticks']) and v[0]!='Z'
 except FileNotFoundError:return False
with (D/'launch.lock').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for name in ['supervisor_identity.json','worker_identity.json']:assert not alive(json.loads((D/name).read_text()))
 oldrec=json.loads((D/'host41_delegation.json').read_text())
 if oldrec.get('destination_root')==x['target'] and oldrec['status']=='delegated_active':
  assert oldrec['pending_manifest']==x['manifest'];print(json.dumps(oldrec));sys.exit(0)
 assert oldrec['status']=='completed_returned'
 old=json.loads((D/'expected_manifest.json').read_text());assert len(old['jobs'])==78
 assert not ({j['id'] for j in old['jobs']}&{j['id'] for j in x['manifest']['jobs']})
 success=[]
 for j in old['jobs']:
  for m in ['instruction_satisfaction','content_fidelity']:
   p=D/'evaluation_awq/results'/j['id']/(m+'.json');v=json.loads(p.read_text());assert v['status']=='done';success.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 assert len(success)==156
 archive=D/'ownership_history'/str(time.time_ns());archive.mkdir(parents=True)
 for n in ['host41_delegation.json','expected_manifest.json','status.json']:(archive/n).write_bytes((D/n).read_bytes())
 merged={**old,'jobs':old['jobs']+x['manifest']['jobs']}
 rec={'status':'delegated_active','destination':'H3_HOST_PRIMARY','destination_root':x['target'],'success_preserved':success,'manifest':merged,'pending_manifest':x['manifest'],'time':time.time(),'purpose':'newly_prepared_incremental_awq'}
 for n,v in [('expected_manifest.json',merged),('host41_delegation.json',rec),('status.json',{'status':'delegated_to_host41','pending_metric_count':20,'time':time.time()})]:
  p=D/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2));t.replace(p)
 print(json.dumps(rec))
'''
release=json.loads(s.remote('H3_HOST_AUXILIARY',claim,data=json.dumps({'target':TARGET,'manifest':selected})));(D/'source_release.json').write_text(json.dumps(release,indent=2));print('Claimed 10 videos, preserved 156 scores',flush=True)
setup=r'''
from pathlib import Path
import shutil,json,sys
r=Path(sys.argv[1]);prior=r.parent/'host60_failover_20261023';r.mkdir(exist_ok=True);(r/'run').mkdir(exist_ok=True)
for n in ['official_source','official_source_sha256.json','weights_verified.json']:
 p=prior/n
 if p.exists() and not (r/n).exists():
  if p.is_dir():shutil.copytree(p,r/n)
  else:shutil.copy2(p,r/n)
# Reuse immutable input frame files already SHA checked by prior batch.
if not (r/'staged').exists():(r/'staged').symlink_to(prior/'staged',target_is_directory=True)
print('target ready')
'''
print(s.remote('H3_HOST_PRIMARY',setup,TARGET),flush=True)
folders={str(Path(j[k])/Path(j['metadata']['src_video_name']).stem) for j in selected['jobs'] for k in ['source_frames_parent','target_frames_parent']};metadata={j['metadata_file'] for j in selected['jobs']}
s.ROOT=D;s.TARGET_HOST='H3_HOST_PRIMARY';s.TARGET_ROOT=TARGET
s.SNAPSHOT_CODE=s.SNAPSHOT_CODE.replace("for receipt in sorted((root/'frames').rglob('PREPARED.json')):","for receipt in [Path(x)/'PREPARED.json' for x in "+repr(sorted(folders))+"]:").replace("for file in sorted((root/'metadata').glob('*.json')):","for file in [Path(x) for x in "+repr(sorted(metadata))+"]:")
s.main(argparse.Namespace(manifest=str(D/'manifest.pending.json')))
snapshot=json.loads((sorted((D/'sync_runs').iterdir())[-1]/'source_snapshot.json').read_text())
for name,value in [('expected_manifest.json',selected),('source_release.json',release),('input_snapshot.json',snapshot)]:
 s.remote(s.TARGET_HOST,'import sys;from pathlib import Path;p=Path(sys.argv[1]);t=p.with_suffix(".tmp");t.write_bytes(sys.stdin.buffer.read());t.replace(p)',TARGET+'/run/'+name,data=json.dumps(value))
print('inputs ready for launch',flush=True)
