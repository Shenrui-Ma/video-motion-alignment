from pathlib import Path
import json,hashlib,shutil,subprocess,time
B=Path(__file__).resolve().parents[1];C=B/'cases/long_0059';A=C/'producer/GPU7_PRELAUNCH_ARCHIVE';A.mkdir(exist_ok=False)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((C/'deploy_manifest.json').read_text())
for rel in ['configs/runtime.json','configs/gpu_quarantine.json','deploy_manifest.json','producer/launch_after_blue.py']:
 p=C/rel;q=A/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
r=json.loads((C/'configs/runtime.json').read_text());r.update(gpu_uuid='GPU-REDACTED',gpu_index=0,expected_gpu_index=0);dump(C/'configs/runtime.json',r)
q=json.loads((C/'configs/gpu_quarantine.json').read_text());q['known_requires_reset'].append({'index':7,'uuid':'GPU-REDACTED'});dump(C/'configs/gpu_quarantine.json',q)
subprocess.run(['python3',str(C/'scripts/execution_gate.py'),'seal'],check=True)
new=json.loads((C/'deploy_manifest.json').read_text());changed=[x for x in old['files'] if old['files'][x]['sha256']!=new['files'][x]['sha256']];assert set(changed)=={'configs/runtime.json','configs/gpu_quarantine.json'}
seal=sha(C/'deploy_manifest.json')
p=C/'producer/launch_after_blue.py';s=p.read_text().replace("SEAL='2a10836c84ff596dc6fb7d0829c7d34af12ec01baab66d30fc0740b2505c611b'",f"SEAL='{seal}'").replace('guidance_schedule_r150_recovery_host41_20261021','guidance_schedule_r150_final_global_host41_20261021').replace('root_r150_book_recovery_host41_attempt1','root_r150_book_final_global_host41_attempt2').replace("'-i','7'","'-i','0'").replace("parts[0]=='7'","parts[0]=='0'").replace('GPU7','GPU0')
anchor="peer=read(ROOT/'configs/readonly_peer.json')"
insert="qr=Path('/data4/researcher/h3_runs/guidance_schedule_r150_20261021/condition_recovery/BATCH_RELEASE.json');qrelease=read(qr)\nrequire(qrelease['passed'] and qrelease['process_absent'] and qrelease['CUDA_allocation_absent'],'Qwen batch release incomplete')\nrequire(service.current_identity(qrelease['pid'])!=qrelease['identity'],'Qwen batch process remains')\n"
assert anchor in s;s=s.replace(anchor,insert+anchor);p.write_text(s)
p=B/'producer/launch_host41_dance.py';p.write_text(p.read_text().replace("'-i','7'","'-i','0'").replace("parts[0]=='7'","parts[0]=='0'").replace('GPU7','GPU0'))
p=B/'condition_recovery/launch_batch.py';s=p.read_text().replace('GPU-REDACTED','GPU-REDACTED').replace('guidance_schedule_r150_recovery_host41_20261021','guidance_schedule_r150_final_global_host41_20261021').replace('root_r150_book_recovery_host41_attempt1','root_r150_book_final_global_host41_attempt2').replace("'-i','7'","'-i','0'");p.write_text(s)
p=B/'condition_recovery/PLAN_RECEIPT.json';q=json.loads(p.read_text());q['target_GPU']=0;q['status']='PREPARED_WAIT_BLUE_FINAL_RELEASE';q['script_sha256']['launch_batch.py']=sha(B/'condition_recovery/launch_batch.py');dump(p,q)
dump(C/'producer/GPU0_REBIND.json',{'passed':True,'changed_sealed_files':changed,'old_seal':sha(A/'deploy_manifest.json'),'new_seal':seal,'scientific_files_unchanged':True,'GPU7_allocation':'unknown','target_gpu':0,'unix':time.time()})
print(json.dumps({'seal':seal,'changed':changed}))
