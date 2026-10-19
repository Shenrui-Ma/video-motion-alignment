"""Preserve the completed portion of R53 as a failed experiment."""
from pathlib import Path
import fcntl,hashlib,json,shutil,time
R=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
P=R/'analysis/postrun';A=P/'captured_failure/step019_admission'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,j):
 with p.open('x') as f:json.dump(j,f,indent=2);f.write('\n')
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cleanup=read(R/'processes/cleanup.json');assert all(cleanup[k] is True for k in ['process_absent','own_compute_absent','child_compute_absent'])
 assert cleanup['service_record']==read(R/'processes/service.json')
 a=read(next((R/'audit/counterfactual').glob('*.json')));c=a['counterfactual'];assert a['status']=='failed' and len(c['steps'])==len(c['measurements'])==19
 assert [x['physical_index'] for x in c['branches'] if x['branch']=='native']==list(range(20))
 rels=set(read(R/'deploy_manifest.json')['files'])|{'deploy_manifest.json'}
 for sub in ['audit','configs','logs','processes','inputs','input','extensions','scripts']:
  rels.update(str(f.relative_to(R)) for f in (R/sub).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
 for rel in rels:assert (R/rel).resolve().is_relative_to(R.resolve()) and (R/rel).is_file()
 start=time.monotonic();A.mkdir(parents=True,exist_ok=False);inv={}
 for rel in sorted(rels):
  src=R/rel;dst=A/rel;dst.parent.mkdir(parents=True,exist_ok=True);before=sha(src);shutil.copyfile(src,dst);assert sha(dst)==sha(src)==before
  inv[rel]={'sha256':before,'bytes':dst.stat().st_size}
 save(A/'FILE_INVENTORY.json',inv)
 receipt={'status':'failed_preserved','failure_step':19,'native_branch_indices':list(range(20)),'completed_response_indices':list(range(19)),'chosen_callback_indices':list(range(19)),'full_branch_indices':[x['physical_index'] for x in c['branches'] if x['branch']=='full'],'sampler_final_present':False,'successful_output_present':False,'process_cleanup_verified':True,'files':len(inv),'bytes':sum(x['bytes'] for x in inv.values()),'inventory_sha256':sha(A/'FILE_INVENTORY.json'),'archive_seconds':time.monotonic()-start,'method_result':'incomplete; no final quality claim'}
 save(A/'FAILURE_ARCHIVE_COMPLETE.json',receipt);print(json.dumps(receipt),flush=True)
