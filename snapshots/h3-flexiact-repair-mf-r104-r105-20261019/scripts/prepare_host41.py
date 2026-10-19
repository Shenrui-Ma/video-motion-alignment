"""Relocate one verified FlexiAct pair and reuse the approved sequential scoring wrapper."""
from pathlib import Path
import argparse,ast,hashlib,json,shutil,subprocess
R=Path(__file__).resolve().parents[1]
T=R.parent/'h3-flexiact-prompt-control-mf-r90-20261019'
OLD=R.parent/'h3-flexiact-character-repair-mf-r98-20261019'
PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def prepare(root):
 root=Path(root).resolve();require(root.is_relative_to(R/'pairs'),'pair outside this metric lane');m=read(root/'prepared/MF_INPUTS.json')
 require(m['comparison_kind']=='actual_paired_guidance' and set(m['targets'])=={'native','guided'},'actual pair required')
 lane=m['lane'];case=m['case'];require(lane in ('r104','r105') and all(x.isalnum() or x=='_' for x in case),'invalid package name')
 dest='/data4/researcher/h3_runs/flexiact_pair_mf_'+lane+'_'+case+'_20261019';package=root/'host41_package';require(not package.exists(),'existing host package retained');package.mkdir()
 for name in ('inputs','prepared','runtime'):shutil.copytree(root/name,package/name)
 for name in ('scripts','audit','configs','tests'):(package/name).mkdir()
 for rel in ('audit/cgroup_memory.py','audit/check_raw_capacity.py','scripts/mf_capacity.py','scripts/process_identity.py'):
  shutil.copy2(T/'host41_package'/rel,package/rel)
 def remote(p):return dest+'/'+str(Path(p).relative_to(package))
 common=(T/'host41_package/scripts/common.py').read_text().replace("CASE='human/one_leg/000'",'CASE='+repr(m['canonical_motion_id']))
 (package/'scripts/common.py').write_text(common)
 for rel in ('scripts/track_shared.py','scripts/tracking_plan.py','audit/run_authorized.py','audit/check_package.py'):
  text=(T/'host41_package'/rel).read_text().replace('R90','REPAIR').replace('r90','repair').replace('old_native','native').replace('new_native','guided')
  if rel=='audit/run_authorized.py':text=text.replace("'comparison_kind':'prompt_control','guidance_used':False","'comparison_kind':'actual_paired_guidance','guidance_used':True")
  ast.parse(text);(package/rel).write_text(text)
 score=(OLD/'scripts/score_one.py').read_text().replace('R98','REPAIR').replace('r98','repair').replace('official-assets human2animal_1/game_man_4 crosspair; score does not certify identity, scene, action type or physical phase',
  'Actual same-source Native/guided comparison; original49@8fps reference and generated0,3,...144; task and event acceptance recorded separately')
 ast.parse(score);(package/'scripts/score_one.py').write_text(score)
 source=read(package/'runtime/official_metric/SOURCE_INPUTS.json');source['inputs'][0]['file']=remote(package/'inputs/official_reference49_8fps.mp4');save(package/'runtime/official_metric/SOURCE_INPUTS.json',source)
 for role in ('native','guided'):
  meta=package/'prepared'/role/'METRIC_INPUTS.json';value=read(meta);value['edited49']=remote(package/'prepared'/(role+'_49_8fps.mp4'));value['full158_output']=remote(package/'inputs'/(role+'_full158.mp4'));value['producer_receipt']['file']=remote(package/'inputs/PAIR_RUNTIME_GATE.json');save(meta,value)
  mapping=package/'prepared'/(role+'_49_8fps.mapping.json');value2=read(mapping);value2.update(source=value['full158_output'],destination=value['edited49']);save(mapping,value2)
  inputs=package/'prepared'/role/'TRACK_INPUTS.json';value3=read(inputs);value3['inputs'][0].update(file=value['edited49'],generation_binding={'metric_inputs':{'file':remote(meta),'sha256':sha(meta)},'release_mapping':{'file':remote(mapping),'sha256':sha(mapping)}});save(inputs,value3)
 match=package/'prepared/guided/MATCHED_GATE_BINDING.json';value=read(match);value['gate']['file']=remote(package/'inputs/PAIR_RUNTIME_GATE.json');save(match,value)
 inheritance=read(root/'configs/NUMERIC_INHERITANCE.json');require(all(sha(package/'runtime/official_metric'/n)==h for n,h in inheritance['files'].items()),'official numeric source changed');save(package/'configs/NUMERIC_INHERITANCE.json',inheritance)
 save(package/'configs/RUNTIME.json',{'remote_root':dest,'python':'/data3/researcher/ComfyUI/.venv/bin/python','GPU':'GPU-REDACTED',
  'GPU_free_GiB':40,'case':m['canonical_motion_id'],'methods':['reference','native','guided'],'scientific_input_parent_sha256':sha(root/'prepared/MF_INPUTS.json'),'status':'CPU_READY_WAIT_COORDINATED_SLOT'})
 capacity=json.loads(subprocess.check_output([PY,str(package/'audit/check_raw_capacity.py'),str(package)],text=True));save(package/'audit/CAPACITY_BOUNDARY_CHECK.json',capacity)
 for file in [*(package/'scripts').glob('*.py'),*(package/'audit').glob('*.py')]:ast.parse(file.read_text())
 files={str(p.relative_to(package)):sha(p) for p in sorted(package.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 save(package/'CONSUMER_FREEZE.json',{'schema':'flex-repair-official-numerics-host41-v1','files':files})
 for name in ('deploy_host41.py','launch_host41.py','collect_host41.py'):
  text=(T/'scripts'/name).read_text().replace('R90','REPAIR').replace('r90','repair').replace('old_native','native').replace('new_native','guided')
  text=text.replace("'human/one_leg/000'",repr(m['canonical_motion_id'])).replace("'comparison_kind':'prompt_control','guidance_used':False","'comparison_kind':'actual_paired_guidance','guidance_used':True")
  text=text.replace('c32897aadc26fff8c251aa269dbbd701e741404a7f84b978ebcfed68f32c549c',m['source_original']['sha256'])
  text=text.replace('Prompt control; visual task/event acceptance remains separate.','Same-source actual Native/guided comparison; visual task/event acceptance recorded separately.')
  ast.parse(text);(root/'scripts').mkdir(exist_ok=True);(root/'scripts'/name).write_text(text)
 print(json.dumps({'package':str(package),'seal_sha256':sha(package/'CONSUMER_FREEZE.json'),'numeric_files':len(inheritance['files']),'capacity_tests':capacity['test_count'],'GPU_started':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('pair_root');a=p.parse_args();prepare(a.pair_root)
