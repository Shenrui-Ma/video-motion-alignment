"""Check cached Euler arithmetic against actual next-step packed-input hashes."""
from pathlib import Path
import fcntl,hashlib,json,os,time
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
import torch
torch.set_num_threads(2)
R=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017');A=R/'analysis/postrun/captured_failure/step019_admission';O=R/'analysis/postrun/audit/cpu_x14_replay'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sig(t):return {'shape':list(t.shape),'dtype':str(t.dtype),'bytes':t.numel()*t.element_size(),'sha256':hashlib.sha256(t.detach().contiguous().numpy().tobytes()).hexdigest()}
def actual(path):
 rel=Path(path).relative_to(R);p=A/rel;assert sha(p)==read(A/'FILE_INVENTORY.json')[str(rel)]['sha256'];return p
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not torch.cuda.is_initialized();O.mkdir(exist_ok=False)
 audit=read(next((A/'audit/counterfactual').glob('*.json')));c=audit['counterfactual'];row=next(r for r in c['inputs'] if r['physical_index']==14)
 x=torch.load(actual(row['file']),map_location='cpu',weights_only=True)['packed'];assert sig(x)==row['packed_signature']
 grid=torch.tensor(c['full_grid'],dtype=torch.float32);rows=[];start=time.monotonic()
 for i in range(14,19):
  chosen=c['steps'][i];data=torch.load(actual(chosen['chosen_file']),map_location='cpu',weights_only=True)
  leaves=[data['video'],data['audio']*4.0];assert [sig(v) for v in leaves]==chosen['chosen_raw_stream_signatures']
  denoised=torch.cat([v.reshape(v.shape[0],1,-1) for v in leaves],dim=-1)
  derivative=(x-denoised)/grid[i].reshape(1,1,1)
  dt=grid[i+1]-grid[i];x=x+derivative*dt
  expected=next(b['same_input'] for b in c['branches'] if b['physical_index']==i+1 and b['branch']=='native')
  rows.append({'update_index':i,'next_index':i+1,'actual':sig(x),'expected':expected,'exact_equal':sig(x)==expected})
  if not rows[-1]['exact_equal']:break
 report={'status':'exact_cpu_replay' if len(rows)==5 and all(r['exact_equal'] for r in rows) else 'cpu_arithmetic_differs','start_index':14,'end_index':rows[-1]['next_index'],'rows':rows,'elapsed_seconds':time.monotonic()-start,'torch':torch.__version__,'device':'cpu','CUDA_initialized':torch.cuda.is_initialized(),'archive_inventory_sha256':sha(A/'FILE_INVENTORY.json'),'no_model_forward':True,'GPU_arithmetic_unverified':True}
 if report['status']=='exact_cpu_replay':
  torch.save({'packed':x,'metadata':report},O/'x19_reconstructed_cpu.pt');report['output']={'file':str(O/'x19_reconstructed_cpu.pt'),'sha256':sha(O/'x19_reconstructed_cpu.pt')}
 (O/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
