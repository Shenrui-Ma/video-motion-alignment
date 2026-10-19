"""One bounded CPU-only check of the already saved pre-intervention branch5."""
from pathlib import Path
import fcntl
import json
import consumer_r12 as consumer

HERE=Path(__file__).resolve().parent
ROOT=Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
RUN='r12_s05_native_observer'
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')

def main():
    code='''import fcntl,hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]);run=sys.argv[2]
p=root/'audit/counterfactual'/f'{run}.json';a=json.loads(p.read_text());branches=a['counterfactual']['branches'];rows=[r for r in branches if r['physical_index']==5 and r['branch']=='native']
if not rows:print(json.dumps({'status':'prefix_not_yet_saved'}));sys.exit(0)
assert len(rows)==1;row=rows[0]
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 os.environ['CUDA_VISIBLE_DEVICES']=''
 import torch
 torch.set_num_threads(1)
 path=root/'audit/counterfactual'/f'{run}_snapshots'/Path(row['file']).name
 assert hashlib.sha256(path.read_bytes()).hexdigest()==row['file_sha256']
 data=torch.load(path,map_location='cpu',weights_only=True)
 parent=json.loads((root/'audit/parent_x0_manifest.json').read_text());old=next(r for r in parent['captures'] if r['step_zero_based']==5)
 checks={}
 for name in ['video','audio']:
  x=data[name];signature={'shape':list(x.shape),'dtype':str(x.dtype),'bytes':x.numel()*x.element_size(),'sha256':hashlib.sha256(x.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
  checks[name+'_actual_tensor_equal_parent']=signature==old[name]
 c=json.loads((root/'audit'/f'{run}_conditioning.json').read_text());b=json.loads((root/'audit/parent_full_conditioning.json').read_text())
 for key in ['prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout']:checks[key]=c[key]==b[key]
 checks['pair_snapshot_actual']=c['pair_snapshot']['actual']==b['pair_snapshot']['actual']
 checks['prefix_nfe_index5']=row['nfe_index']==5
 checks['global_rng_unchanged']=all(r['global_rng_unchanged'] for r in branches)
 result={'status':'live_prefix_checked','passed':all(checks.values()),'checks':checks,'actual_current_status':a['status'],'observed_model_forwards':a['completed_forward_calls'],'prefix_file':str(path),'prefix_file_sha256':row['file_sha256'],'scope':'Read-only actual prefix5 and prepared-condition audit during sampling; not final replay or efficacy acceptance.'}
 print(json.dumps(result))
'''
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        output=consumer.shell('H3_SERVER_A',['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','/home/researcher/miniconda3/envs/comfyui/bin/python','-c',code,str(ROOT),RUN])
    result=json.loads(output);consumer.save(HERE/'replication/live_prefix_gate.json',result)
    print(json.dumps(result))

if __name__=='__main__':main()
