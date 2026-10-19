"""Validate all actual R9 stored tensors, CPU only, without claiming decoded pose."""
from pathlib import Path
import json
import consumer_r9 as consumer

HERE=Path(__file__).resolve().parent
REMOTE=Path('/data3/researcher/h3_runs/timing_hold_control_r9_20261016')
RUN='r9_s05_hold2'
EXPECTED=[5,6,7,8,9,10,15,19]


def main():
    code='''import hashlib,json,os,sys
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
torch.set_num_threads(1)
root=Path(sys.argv[1]);run=sys.argv[2];folder=root/'audit/x0'/run
m=json.loads((folder/'manifest.json').read_text());expected=[5,6,7,8,9,10,15,19]
assert m['status']=='complete' and m['run_id']==run
entries=m['captures']+[m['final_sampler_result']]
assert [x['file'] for x in m['captures']]==[f'x0_step{i:03d}.pt' for i in expected]
assert m['final_sampler_result']['file']=='sampler_final.pt'
rows=[]
for entry in entries:
 p=folder/entry['file'];v=torch.load(p,map_location='cpu',weights_only=True);checks={};streams={}
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
out=root/'analysis/pose/replication/capture_inventory.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'tensor_files':len(rows)}))
if not result['passed']:raise ValueError('Capture inventory failed')
'''
    print(consumer.shell('H3_SERVER_B',['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','/data3/researcher/ComfyUI/.venv/bin/python','-c',code,str(REMOTE),RUN]),flush=True)
    consumer.copy_from('H3_SERVER_B',REMOTE/'analysis/pose/replication/capture_inventory.json',HERE/'replication/capture_inventory.json')
    consumer.copy_from('H3_SERVER_B',REMOTE/'audit/x0'/RUN/'manifest.json',HERE/'replication/capture_manifest.json')


if __name__=='__main__':main()
