"""Run only the two authorized existing R12 VAE decodes, sequentially."""
import fcntl, hashlib, json, os, subprocess, time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
O=R/'analysis/pose/x0_decoded'
UUID='GPU-REDACTED'
PY='/home/researcher/miniconda3/envs/comfyui/bin/python'
D=R/'scripts/decode_x0.py'
EXPECTED={10:'4e0ad90ebf903721ae488d8220524fe07dcf646bdf5c843cf634ae169755d56c',15:'e8adcacc930d004f32838af0b96ff19ce13f312d54c275150908fedaffd6a04b'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(v):(O/'pair_execution.json').write_text(json.dumps(v,indent=2)+'\n')
def snapshot():
 return {'gpu':subprocess.check_output(['nvidia-smi','--id='+UUID,'--query-gpu=uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),'compute':subprocess.check_output(['nvidia-smi','--id='+UUID,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()}
def main():
 O.mkdir(parents=True,exist_ok=True)
 with (O/'decode_pair.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if (O/'pair_execution.json').exists():raise RuntimeError('Existing execution must be inspected, never duplicated')
  if any(Path('/proc/'+str(p)).exists() for p in [22793,22790,23635,23634]):raise RuntimeError('R13 process remains')
  assert sha(D)=='799e64e1d2e1dab3582fe4600fea810c388facbab447fd0887dc51f4a1494014'
  record={'run_id':'r12_s05_native_observer','status':'running','indices':[10,15],'pid':os.getpid(),'nfe':0,'dit_started':False,'decoder_sha256':sha(D),'before':snapshot(),'started_unix':time.time(),'rows':[]}
  save(record)
  try:
   for index in [10,15]:
    stem=f'x0_step{index:03d}';source=R/'audit/x0/r12_s05_native_observer'/(stem+'.pt')
    if sha(source)!=EXPECTED[index]:raise ValueError('Snapshot file hash differs')
    args=[PY,'-u',str(D),str(source),'--core','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--runtime-deps','/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps','--vae','/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors','--expected-vae-sha256','7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522','--gpu-uuid',UUID,'--output',str(O/(stem+'.mp4'))]
    env=os.environ.copy()
    for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='4'
    t=time.time()
    with (O/(stem+'.log')).open('w') as log:
     process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env)
     row={'index':index,'pid':process.pid,'command':args,'started_unix':t};record['rows'].append(row);save(record)
     rc=process.wait()
    row.update(exit_code=rc,finished_unix=time.time(),wall_seconds=time.time()-t,pid_absent=not Path('/proc/'+str(process.pid)).exists(),gpu_after=snapshot())
    save(record)
    if rc:raise RuntimeError('Decoder failed; evidence retained')
    data=json.loads((O/(stem+'.json')).read_text())
    if data['status']!='complete' or data['snapshot_sha256']!=EXPECTED[index] or sha(O/(stem+'.mp4'))!=data['output_sha256']:raise ValueError('Decode output record mismatch')
    if row['gpu_after']['compute']:raise RuntimeError('GPU compute remains after decoder exit')
    print(json.dumps({'completed':stem,'wall_seconds':row['wall_seconds'],'gpu_after':row['gpu_after']}),flush=True)
   record['status']='complete'
  except BaseException as e:
   record['status']='failed';record['error']=repr(e);raise
  finally:
   record['finished_unix']=time.time();record['after']=snapshot();save(record)
if __name__=='__main__':main()
