from pathlib import Path
import hashlib,json,tarfile
r=Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017')
stage=Path('/data3/researcher/h3_runs/r54_root_stage')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bundle=stage/'runtime_bundle_v1.tar.gz'
assert sha(bundle)=='d881df84c20107be287cbd75968df3d6966bef1ef9609422239068fc9eca7fd6'
assert not (r/'deploy_manifest.json').exists()
with tarfile.open(bundle) as tf:
 members=tf.getmembers();assert sum(m.isfile() for m in members)==56
 for m in members:
  assert not m.name.startswith('/') and '..' not in Path(m.name).parts and (m.isfile() or m.isdir())
  assert not m.name.startswith('inputs/'),m.name
  if m.isfile() and (r/m.name).exists():
   assert sha(r/m.name)==hashlib.sha256(tf.extractfile(m).read()).hexdigest(),m.name
 tf.extractall(r)
assert sha(r/'deploy_manifest.json')=='159247ee989ea98a4f73efa8aeb0be8c95263aeee79872e65ab8a1dd2a72d9f6'
m=json.loads((r/'deploy_manifest.json').read_text());pending=[];verified=[]
for name,e in m['files'].items():
 p=r/name
 if name.startswith('inputs/') and not p.exists():pending.append(name);continue
 assert sha(p)==e['sha256'],name
 verified.append(name)
result={'verified_files':len(verified),'pending_input_files':pending,'GPU_started':False}
(r/'audit/root_deploy.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
