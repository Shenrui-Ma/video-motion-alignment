from pathlib import Path
import argparse,fcntl,json,os,subprocess,sys,time,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--lock',default='/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock');args=parser.parse_args()
lock=Path(args.lock)
with lock.open('a+') as handle:
 try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('BUSY_CPU_LOCK');raise SystemExit(75)
 t=time.monotonic();os.chdir(root/'metric_runtime');sys.path.insert(0,str(root/'metric_runtime'))
 from ive_mf_adapter import official_class,WEIGHT_SHA,sha,verify_vendor
 import torch
 torch.set_num_threads(1)
 cp=root/'weights/baseline_offline.pth';assert sha(cp)==WEIGHT_SHA
 assert not torch.cuda.is_initialized()
 cls=official_class();model=cls(str(cp),device='cpu',grid_size=10,max_frames=None)
 assert not torch.cuda.is_initialized()
 result={'checkpoint_sha256':sha(cp),'official_vendor':verify_vendor(),'adapter_sha256':sha(root/'metric_runtime/ive_mf_adapter.py'),'test_sha256':sha(root/'metric_runtime/test_official_mf.py'),'model_construction':'PASS','parameters':sum(x.numel() for x in model.model.parameters()),'device':'cpu','cuda_initialized':torch.cuda.is_initialized(),'tracking_forwards':0,'torch_version':torch.__version__}
 tests=subprocess.run([sys.executable,str(root/'metric_runtime/test_official_mf.py'),'-v'],capture_output=True,text=True,env=os.environ.copy())
 (root/'CPU_TEST.txt').write_text(tests.stdout+tests.stderr)
 result.update(test_exit_code=tests.returncode,seconds=time.monotonic()-t)
 (root/'CPU_COMPATIBILITY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(tests.returncode)
