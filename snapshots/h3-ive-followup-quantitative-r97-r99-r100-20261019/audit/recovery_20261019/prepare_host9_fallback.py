"""CPU-only fallback package; no launcher and no source cache from a different runtime."""
from pathlib import Path
import hashlib,json,shutil,ast,subprocess,shlex
H=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
name='r106_short_0252_solvers';old=H/name;r=H/(name+'_host9');assert not r.exists()
s=read(old/'SEAL.json')
for n,h in s['files'].items():assert sha(old/n)==h
shutil.copytree(old,r);(r/'SEAL.json').rename(r/'audit/HOST41_SEAL.json')
# No stale .41 generation barrier or executable wrapper can launch this fallback.
(r/'audit/run_authorized.py').rename(r/'audit/HOST41_WRAPPER_REFERENCE.txt');(r/'audit/check_package.py').rename(r/'audit/HOST41_CHECK_REFERENCE.txt')
p=r/'configs/RUNTIME.json';c=read(p);c.update(remote_root='/home/researcher/h3_runs/ive_r106_sampler_mf_host9_20261019',python='/home/researcher/miniconda3/envs/comfyui/bin/python',checkpoint='/data5/researcher/h3_runs/ivebench_forced_metrics_r63_20261018/runtime/weights/baseline_offline.pth',host='zgc-33-9',uid=1016,planned_gpu_uuid='GPU-REDACTED',GPU_execution_status='CPU_READY_WAIT_R105_RELEASE_AND_ROOT_COORDINATION');p.write_text(json.dumps(c,indent=2)+'\n')
p=r/'scripts/common.py';t=p.read_text();start=t.index(" cg=Path('/sys/fs/cgroup/user.slice');");end=t.index('\n return ',start);t=t[:start]+" require(not any(x['uid']==os.getuid() and x['gpu_uuid']==gpu for x in rows),'own H3 process still on selected GPU')\n mem={k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())};available=int(mem['MemAvailable'].split()[0])*1024;require(available>=32*2**30,'host memory below32GiB');c={'host_available_bytes':available,'GPU_status':'fresh ordinary tracker requires exact root slot'}"+t[end:];ast.parse(t);p.write_text(t)
check='''from pathlib import Path
import sys,json
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));import common as c
c.verify_seal();c.verify_runtime();case=next((r/'cases').iterdir());s=c.read(case/'SPEC.json');m=c.read(case/'INPUTS.json');assert not s.get('source_cache_reuse');c.validate_gate(s,c.read(case/s['gate']['file']))
assert m['valid_frames']==98 and set(m['roles'])=={'source','euler','res_multistep'}
for v in m['roles'].values():assert c.sha(case/v['full_file'])==v['full_sha256'] and c.sha(case/v['score_file'])==v['score_sha256']
assert 'torch' not in sys.modules;assert not (r/'audit/run_authorized.py').exists();print(json.dumps({'passed':True,'CUDA_started':False,'frame_count':98,'roles':list(m['roles']),'input_sha256':c.sha(case/'INPUTS.json')}))
''';(r/'audit/check_package.py').write_text(check)
for n,h in s['files'].items():
 if n.startswith(('cases/','runtime/')):assert sha(r/n)==h,n
(r/'audit/HOST9_PLAN.json').write_text(json.dumps({'CPU_only':True,'source_and_both_targets_fresh':True,'official_checkpoint_sha256':'da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df','prior_host9_runtime':'torch2.5.1+cu121','prior_host41_runtime':'torch2.11+cu130','original_scientific_input_sha256':sha(old/'cases'/name/'INPUTS.json'),'requirements':['root exact R105 release','coordinate remaining R104 process admission','only one tracker at once','own GPU cap2','fresh 24GiB free GPU/32GiB host check','actual final PID and CUDA absence'],'launch_wrapper_created':False},indent=2)+'\n')
files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};(r/'SEAL.json').write_text(json.dumps({'schema':'ive-mf-host9-fallback-cpu-v1','files':files},indent=2)+'\n')
subprocess.run(['/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python',str(r/'audit/check_package.py'),str(r)],check=True)
print(json.dumps({'package':str(r),'seal':sha(r/'SEAL.json'),'GPU_started':False}))
