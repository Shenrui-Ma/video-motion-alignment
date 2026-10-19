import ast,hashlib,json,sys,tarfile
from pathlib import Path
r=Path(__file__).resolve().parents[1];attempt=int(sys.argv[1]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());put=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
result=read(r/'audit'/f'real_comfy_cpu_attempt{attempt}.json');assert result['exit']==0
log=r/'audit'/f'real_comfy_cpu_attempt{attempt}.log';assert sha(log)==result['log_sha256']
line=[s for s in log.read_text().splitlines() if s.startswith('H3_STATIC_WINDOW_CPU_SMOKE=')];assert len(line)==1
v=json.loads(line[0].split('=',1)[1]);assert v['success'] and not v['CUDA_initialized'] and v['actual_seed1313_noise_cold_hit_pass'] and v['online_observations']==0
assert len(v['cases'])==1 and v['cases'][0]['NFE']==21 and v['cases'][0]['callbacks']==20 and v['cases'][0]['actual_mask']==[4]
stage=read(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json');py={name:h for name,h in stage['files'].items() if name.endswith('.py')};assert all(sha(r/name)==h for name,h in py.items())
assert v['core_sha256']==sha(r/'extensions/H3StaticWindowRouter/core.py')
for n,h in read(r/'audit/original_design_hashes.json').items():assert sha(r/n)==h
for n,h in py.items():ast.parse((r/n).read_text(),filename=n)
put(r/'configs/CPU_EVIDENCE.json',{'schema':'r37-actual-comfy-cpu-evidence-v1','passed':True,'attempt':attempt,'log_sha256':sha(log),'stage_manifest_sha256':sha(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json'),'runtime_python_exact_to_stage':py,'actual_interface':v,'wall_seconds_including_lock_staging':result['seconds'],'local_unit_log_sha256':sha(r/'audit/unit_attempt1.log'),'scope':'Official Comfy loader/ModelPatcher/BasicGuider/Euler/wrappers + real H3 cond types and AV shapes, synthetic tiny QKV/model; actual frozen seed1313 cold noise. No H3 weights, historical native tensors, GPU numerical or trajectory test is claimed.'})
sys.path.insert(0,str(r/'scripts'));from build_manifest import build
seal=build(r);put(r/'audit/SEAL.json',seal)
with tarfile.open(seal['bundle']) as tf:
 names=[x.name for x in tf.getmembers()];manifest=read(r/'deploy_manifest.json');wanted=[n for n in manifest['files'] if not n.startswith('inputs/')]+['deploy_manifest.json','configs/admission.json','configs/queue.json'];assert sorted(names)==sorted(wanted)
 for n in names:assert hashlib.sha256(tf.extractfile(n).read()).hexdigest()==sha(r/n)
put(r/'audit/FINAL_HANDOFF_CHECK.json',{'passed':True,'producer':seal,'tar_exact_members':len(names),'stage_python_count':len(py),'original_design_unchanged':True,'metadata_preflight':True,'GPU_started':False,'postrun_parent_Auto_actual_binding':'actual R27 normal all-OFF artifacts bound; no R32 or badseed output used'})
print(json.dumps(seal,indent=2))
