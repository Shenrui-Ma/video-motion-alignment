from pathlib import Path
import os,sys,json,time,socket,hashlib,subprocess,argparse
parser=argparse.ArgumentParser();parser.add_argument('--launch',action='store_true');args=parser.parse_args()
r=Path('/home/researcher/h3_runs/timing_ive_caption_ablation_r130_20261020');sys.path.insert(0,str(r/'scripts'));import service
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
assert read(r/'audit/TARGET_CPU_READY.json')['passed'];manifest=read(r/'deploy_manifest.json');assert H(r/'deploy_manifest.json')=='89e7168d98d12e9a6b8b29e77ce6a70dacd72fc867863eba461877d60f6e93e4'
for f,v in manifest['files'].items():assert H(r/f)==v['sha256'],f
prior=r.parent/'timing_ive_handkerchief_full_context_r126_20261020/audit/root_handkerchief_full_context_attempt1/ROOT_EXIT_RECEIPT.json';pv=read(prior);assert pv['passed'] and pv['process_absent'] and pv['CUDA_allocation_absent'];assert service.current_identity(pv['owner']['pid']) is None
noise=read(r/'audit/ACTUAL_R124_NOISE_REUSE.json');assert noise['passed'] and H(Path(noise['source']))==H(Path(noise['target']))==noise['file_sha256']
peer=r.parent/'timing_ive_aligned_media_clock_r129_20261020';owner=read(peer/'processes/service.json');assert owner['pid']==33719 and owner['identity']['start_ticks']=='2647509646';identity=service.current_identity(owner['pid']);peers=[]
if identity is not None:assert identity==owner['identity'];peers=[peer]
raw=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True);gpu=next(x.split(', ') for x in raw.strip().splitlines() if x.split(', ')[0]=='3');assert gpu[1]=='GPU-REDACTED' and int(gpu[2])>=40960
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],text=True);own=[]
for line in apps.strip().splitlines():
 pid=int(line.split(',')[0]);ident=service.current_identity(pid)
 if ident and ident['uid']==os.getuid():own.append({'pid':pid,'identity':ident,'line':line})
expected={owner['pid']} if peers else set();assert {v['pid'] for v in own}<=expected,own
s=socket.socket();s.settimeout(1);assert s.connect_ex(('127.0.0.1',8606))!=0;s.close();assert not (r/'processes/service.json').exists()
v={'passed':True,'prior_release':{'file':str(prior),'sha256':H(prior)},'noise_receipt_sha256':H(r/'audit/ACTUAL_R124_NOISE_REUSE.json'),'seal_sha256':H(r/'deploy_manifest.json'),'peer':owner if peers else None,'gpu':gpu,'own_compute':own,'port8606_empty':True,'unix':time.time(),'attempt':'root_caption_ablation_attempt1'};(r/'audit/DISPATCH_FRESH.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
if args.launch:
 env=dict(os.environ,PATH=str(Path(sys.executable).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C');cmd=[sys.executable,'-u','audit/root_run_batch.py','--execute','--attempt','root_caption_ablation_attempt1']
 for peer in peers:cmd += ['--peer-root',str(peer)]
 with (r/'logs/root_wrapper.log').open('ab',buffering=0) as log:p=subprocess.Popen(cmd,cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 print(json.dumps({'wrapper_pid':p.pid,'attempt':v['attempt']}))
