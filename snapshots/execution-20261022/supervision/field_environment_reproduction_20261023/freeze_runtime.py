from pathlib import Path
import json,hashlib,subprocess,shlex,time
from check_science import D,E,R,sha
files={('scripts/'+n):(D/n).read_bytes().hex() for n in ['field_gate.py','field_supervisor.py']}
code=r'''
from pathlib import Path
import json,hashlib,sys,time,subprocess,fcntl,socket
r=Path(ROOT);data=json.load(sys.stdin);assert not (r/'STARTED.json').exists() and not (r/'jobs').exists()
for k,v in data.items():
 p=r/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(bytes.fromhex(v));compile(p.read_text(),str(p),'exec')
policy=json.loads((r/'shared_gpu_authorization.json').read_text());assert (policy['torch_allocator_cap_gib'],policy['reserve_vram_gib'],policy['minimum_free_mib'],policy['post_context_external_headroom_mib'])==(19.5,6,22500,1536)
rows=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
others=[]
for line in apps.splitlines():
 if policy['gpu_uuid'] not in line:continue
 a=[x.strip() for x in line.split(',')];p=Path('/proc')/a[1];st=(p/'stat').read_text().rsplit(')',1)[1].split();others.append({'pid':int(a[1]),'uid':p.stat().st_uid,'start_ticks':st[19],'used_mib':a[2]})
assets={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['scripts','custom_nodes/H3Study','custom_nodes/H3TrustedConditionCache','custom_nodes/H3LivePhase','custom_nodes/H3TemporalGainField','graphs'] for p in (r/base).glob('*.py' if base!='graphs' else '*.json')}
for n in ['jobs.json','SCIENCE_CHECK.json','SCIENCE_READY.json','INPUT_IDENTITY.json','gpu.json','shared_gpu_authorization.json','MODEL_REHASH.json']:assets[n]=hashlib.sha256((r/n).read_bytes()).hexdigest()
lock=open('/tmp/h3-video-inference-research-user-'+policy['gpu_uuid']+'.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.close()
with socket.socket() as s:s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',8687))
out={'status':'review_pending_not_submitted','time':time.time(),'root':str(r),'gpu_row':next(x for x in rows.splitlines() if policy['gpu_uuid'] in x),'protected_processes':others,'gpu_lock_free':True,'api_port_free':True,'assets':assets,'policy':policy,'first_forward_gate':'50 independently checked finite applied layers plus actual same-runtime Triton calls; failure stops own service and retains single attempt','completion_gate':'20 forwards x 50 blocks; independent frozen field QP/anchor/KKT; exact graph and output SHA; actual timing/own peak; Triton4000 CUDA0 eager0 observed, no assumed dispatch','terminal_backend_note':'After successful history no further model job is submitted; 4000th periodic flush is required. Service then exits; terminal snapshot saved separately.','maximum_attempts':1}
(r/'RUNTIME_CONTRACT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh','H3_HOST_RTX4090','python3 -c '+shlex.quote(code)],input=json.dumps(files),capture_output=True,text=True,timeout=60);assert p.returncode==0,p.stderr;o=json.loads(p.stdout);(D/'RUNTIME_CONTRACT.json').write_text(json.dumps(o,indent=2)+'\n');(D/'DEPLOY_ASSETS.json').write_text(json.dumps(o['assets'],indent=2)+'\n');print({k:o[k] for k in ['status','gpu_row','protected_processes','gpu_lock_free','api_port_free']})
