import json,os,subprocess,time
from pathlib import Path
r=Path('/data5/researcher/h3_runs/flexiact_vae_roundtrip_r67_20261018/analysis/fitness_x0_diagnostic')
a=r/'audit/root_batch_attempt1';a.mkdir(parents=True,exist_ok=False)
python='/home/researcher/miniconda3/envs/comfyui/bin/python'
gpu='GPU-REDACTED'
done=[]
for arm,index in [('native',2),('native',5),('native',6),('forced',6)]:
 key=f'{arm}_step{index:03d}_attempt1';out=r/'outputs'/key
 argv=[python,'-u',str(r/'scripts/decode_saved_x0.py'),'--run-id',f'r65_fitness_seed2026101701_{arm}','--index',str(index),'--gpu-uuid',gpu,'--output',str(out),'--execute']
 with (a/(key+'.log')).open('xb') as f:
  child=subprocess.Popen(argv,env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu),stdin=subprocess.DEVNULL,stdout=f,stderr=f)
  code=child.wait(timeout=900)
 assert code==0,(key,code)
 v=json.loads((out/'RESULT.json').read_text());assert v['status']=='complete' and v['pid']==child.pid
 assert not Path('/proc',str(child.pid)).exists()
 apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True)
 assert str(child.pid) not in apps.splitlines()
 rec={'key':key,'pid':child.pid,'process_absent':True,'CUDA_allocation_absent':True,'decode_seconds':v['decode_seconds'],'peak_reserved_bytes':v['max_memory_reserved_bytes'],'unix':time.time()};done.append(rec)
 (a/'PROGRESS.json').write_text(json.dumps(done,indent=2)+'\n');print(json.dumps(rec),flush=True)
(a/'COMPLETE.json').write_text(json.dumps({'passed':True,'completed':done,'unix':time.time()},indent=2)+'\n')
