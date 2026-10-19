"""Validate all actual R12 stored tensors, CPU only, without claiming decoded pose."""
from pathlib import Path
import json
import argparse
import consumer_r12 as consumer

HERE=Path(__file__).resolve().parent
REMOTE=Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
RUN=None
EXPECTED=[5,6,7,8,9,10,15,19]


def main():
    global RUN
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args();RUN=consumer.formal_run(args.run_id)
    code='''import hashlib,json,os,sys
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
torch.set_num_threads(1)
root=Path(sys.argv[1]);run=sys.argv[2];folder=root/'audit/x0'/run
m=json.loads((folder/'manifest.json').read_text());expected=[5,6,7,8,9,10,15,19]
assert m['status']=='complete' and m['run_id']==run
assert m['callback_count']==20
assert m['capture_steps_zero_based']==expected
assert [entry['step_zero_based'] for entry in m['captures']]==expected, 'Actual capture indices differ from exact eight-item inventory'
assert len({entry['file'] for entry in m['captures']})==8, 'Duplicate capture filenames'
entries=m['captures']+[m['final_sampler_result']]
assert [x['file'] for x in m['captures']]==[f'x0_step{i:03d}.pt' for i in expected]
assert m['final_sampler_result']['file']=='sampler_final.pt'
assert {p.name for p in folder.glob('*.pt')}=={entry['file'] for entry in entries}, 'Unexpected or missing independent tensor files'
rows=[]
for entry in entries:
 p=folder/entry['file'];v=torch.load(p,map_location='cpu',weights_only=True);checks={};streams={}
 final=entry['file']=='sampler_final.pt';step=19 if final else entry['step_zero_based'];meta=v['metadata']
 checks['metadata_run']=meta['run_id']==run
 checks['metadata_step']=meta['step_zero_based']==step and meta['model_call_one_based']==step+1
 checks['metadata_kind']=meta['snapshot_kind']==('sampler_final' if final else 'x0_estimate')
 checks['metadata_total_steps']=meta['total_steps']==20
 for name,shape in [('video',[1,24,42,46,82]),('audio',[1,32,2,235])]:
  x=v[name];raw=hashlib.sha256(x.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
  checks[name+'_manifest_hash']=raw==entry[name]['sha256']
  checks[name+'_finite']=bool(torch.isfinite(x).all())
  checks[name+'_dtype']=str(x.dtype)=='torch.float32'
  checks[name+'_recorded_shape']=list(x.shape)==entry[name]['shape']
  checks[name+'_expected_shape']=list(x.shape)==shape
  streams[name]={'shape':list(x.shape),'dtype':str(x.dtype),'sha256':raw}
 rows.append({'file':entry['file'],'file_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'metadata':v['metadata'],'streams':streams,'checks':checks,'passed':all(checks.values())})
result={'run_id':run,'manifest_sha256':hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),'captured_indices_zero_based':expected,'original_indices':[5,10,15,19],'added_indices':[6,7,8,9],'rows':rows,'passed':all(r['passed'] for r in rows),'scope':'Actual saved finite tensor/manifest validation. No independent image/pose conclusion for un-decoded captures.','gpu_started':False}
out=root/'analysis/pose/replication'/run/'capture_inventory.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'tensor_files':len(rows)}))
if not result['passed']:raise ValueError('Capture inventory failed')
'''
    print(consumer.shell('H3_SERVER_A',['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','/home/researcher/miniconda3/envs/comfyui/bin/python','-c',code,str(REMOTE),RUN]),flush=True)
    consumer.copy_from('H3_SERVER_A',REMOTE/'analysis/pose/replication'/RUN/'capture_inventory.json',HERE/'replication'/RUN/'capture_inventory.json')
    consumer.copy_from('H3_SERVER_A',REMOTE/'audit/x0'/RUN/'manifest.json',HERE/'replication'/RUN/'capture_manifest.json')


if __name__=='__main__':main()
