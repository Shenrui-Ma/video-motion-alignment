from pathlib import Path
import json,hashlib,shutil,tarfile,os,time
R=Path('/data5/researcher/h3_runs/timing_source51310_prompt_pair_r75_20261018');A=R/'audit/gpu0_migration';A.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((R/'deploy_manifest.json').read_text())
assert sha(R/'deploy_manifest.json')=='65a248b9390bfdbbf6c4e4f2ed3bfa2ee2f553d3897afb48e09f3555038ab422'
assert all(sha(R/p)==v['sha256'] for p,v in old['files'].items())
patterns=['processes/*.json','logs/*_job.json','logs/*_history.json','output/*.mp4','audit/ROOT_FIRST_PAIR_APPROVAL.json','analysis/postrun/*/PAIR_RUNTIME_GATE.json']
assert not any(list(R.glob(x)) for x in patterns)
assert json.loads((R/'configs/admission.json').read_text())['ready_for_launch'] is False
archive=A/'before_gpu1';archive.mkdir(exist_ok=True)
paths=list(old['files'])+['deploy_manifest.json']+(['ROOT_HANDOFF.txt'] if (R/'ROOT_HANDOFF.txt').exists() else [])+[str(p.relative_to(R)) for p in (R/'audit/consumer').glob('*.py')]
for rel in paths:
 p=archive/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert sha(p)==sha(R/rel)
 else:shutil.copy2(R/rel,p)
stage=A/'stage';stage.mkdir(exist_ok=False)
allowed={'configs/runtime.json','configs/scientific_contract.json','scripts/launch_remote.py','scripts/service.py','scripts/start_controller.py','deploy_manifest.json','ROOT_HANDOFF.txt'}
with tarfile.open(R/'audit/GPU0_REVISION.tar.gz') as t:
 assert {m.name for m in t.getmembers()}==allowed
 for m in t.getmembers():
  assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
  target=stage/m.name;target.parent.mkdir(parents=True,exist_ok=True)
  with t.extractfile(m) as src, target.open('xb') as out:shutil.copyfileobj(src,out)
new=json.loads((stage/'deploy_manifest.json').read_text())
assert sha(stage/'deploy_manifest.json')=='1b1f867dc259a3729a44deddc944b4c60a2d3a68b03c3bfa476bf888f6f9098c'
for rel in allowed-{'deploy_manifest.json'}:
 temporary=(R/rel).with_suffix((R/rel).suffix+'.gpu0_revision_tmp');shutil.copy2(stage/rel,temporary);temporary.replace(R/rel)
assert all(sha(R/p)==v['sha256'] for p,v in new['files'].items())
temporary=R/'deploy_manifest.gpu0_revision_tmp';shutil.copy2(stage/'deploy_manifest.json',temporary);temporary.replace(R/'deploy_manifest.json')
(R/'temp_os').mkdir(exist_ok=True)
record={'schema':'r75-gpu0-passive-deployment-v1','unix':time.time(),'old_seal':sha(archive/'deploy_manifest.json'),'new_seal':sha(R/'deploy_manifest.json'),'archived_files':len(paths),'new_files_verified':len(new['files']),'runtime':json.loads((R/'configs/runtime.json').read_text()),'no_jobs_or_service_before_update':True,'admission_remains_false':json.loads((R/'configs/admission.json').read_text())['ready_for_launch'] is False,'gpu_started':False,'consumer_code_unchanged':all(sha(R/p)==sha(archive/p) for p in paths if p.startswith('audit/consumer/'))}
(A/'DEPLOYMENT.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
