"""Build a relocated R90 official-MF package with unchanged numeric source."""
from pathlib import Path
import json,hashlib,shutil,ast
R=Path(__file__).resolve().parents[1];P=R/'host41_package';DEST='/data4/researcher/h3_runs/flexiact_prompt_control_mf_r90_20261019';OLD=R.parent/'h3-flexiact-character-repair-mf-r98-20261019';IVE=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r106_short_0252_solvers_capacity4';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def remote(p):return DEST+'/'+str(Path(p).relative_to(P))
assert not P.exists();P.mkdir()
for folder in ['inputs','prepared','runtime']:
 shutil.copytree(R/folder,P/folder)
(P/'scripts').mkdir();(P/'audit').mkdir();(P/'configs').mkdir();(P/'tests').mkdir()
for rel in ['audit/cgroup_memory.py','scripts/mf_capacity.py','audit/check_raw_capacity.py','scripts/process_identity.py']:shutil.copy2(IVE/rel,P/rel)
common=(OLD/'scripts/common.py').read_text().replace("CASE='human/human2animal_1/000'","CASE='human/one_leg/000'");(P/'scripts/common.py').write_text(common)
t=(OLD/'scripts/track_shared.py').read_text().replace('R98','R90').replace('r98','r90');t=t.replace('return {\'observed_unix\': time.time()',"from mf_capacity import check as capacity\n    cgroup = capacity(8)\n    return {'cgroup': cgroup, 'observed_unix': time.time()")
t=t.replace("finally:\n        if", "finally:\n        import resource\n        save(Path(args.control) / 'PROCESS_USAGE.json', {'maxrss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'identity': identity(), 'pid': os.getpid()})\n        if");ast.parse(t);(P/'scripts/track_shared.py').write_text(t)
source=read(P/'runtime/official_metric/SOURCE_INPUTS.json');source['inputs'][0]['file']=remote(P/'inputs/official_reference49_8fps.mp4');save(P/'runtime/official_metric/SOURCE_INPUTS.json',source)
for role in ['old_native','new_native']:
 meta=P/'prepared'/role/'METRIC_INPUTS.json';m=read(meta);m['edited49']=remote(P/'prepared'/f'{role}_49_8fps.mp4');m['full158_output']=remote(P/'inputs'/f'{role}_full158.mp4');m['producer_receipt']['file']=remote(P/'inputs'/('P0_GATE.json' if role=='old_native' else 'P1_GATE.json'));save(meta,m)
 mapping=P/'prepared'/f'{role}_49_8fps.mapping.json';mp=read(mapping);mp['source']=m['full158_output'];mp['destination']=m['edited49'];save(mapping,mp)
 inputs=P/'prepared'/role/'TRACK_INPUTS.json';d=read(inputs);it=d['inputs'][0];it['file']=m['edited49'];it['generation_binding']={'metric_inputs':{'file':remote(meta),'sha256':sha(meta)},'release_mapping':{'file':remote(mapping),'sha256':sha(mapping)}};save(inputs,d)
plan='''import argparse,shlex\nfrom common import *\ndef command(method,gpu,python):\n verify_runtime();require(method in ['reference','old_native','new_native'],'unknown method');manifest=METRIC/'SOURCE_INPUTS.json' if method=='reference' else ROOT/'prepared'/method/'TRACK_INPUTS.json';control=ROOT/'controls'/method;output=ROOT/'tracks'/method;require(not control.exists() and not output.exists(),'prior attempt retained');return ['env','CUDA_VISIBLE_DEVICES='+gpu,'OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',python,str(ROOT/'scripts/track_shared.py'),'--control',str(control),'--','--input-manifest',str(manifest),'--case',CASE,'--gpu-uuid',gpu,'--output',str(output)]\nif __name__=='__main__':\n p=argparse.ArgumentParser();p.add_argument('--method',required=True);p.add_argument('--gpu-uuid',required=True);p.add_argument('--python',default='/data3/researcher/ComfyUI/.venv/bin/python');a=p.parse_args();print(json.dumps({'argv':command(a.method,a.gpu_uuid,a.python),'CUDA_started':False}))\n''';(P/'scripts/tracking_plan.py').write_text(plan)
score=(OLD/'scripts/score_one.py').read_text().replace('R98','R90').replace('r98','r90').replace("method in ['native','guided']","method in ['old_native','new_native']").replace("choices=['native','guided']","choices=['old_native','new_native']")
score=score.replace(" if method=='guided':require((ROOT/'prepared/guided/MATCHED_GATE_BINDING.json').is_file(),'actual guided binding pending')\n",'').replace("official-assets human2animal_1/game_man_4 crosspair; score does not certify identity, scene, action type or physical phase","official-assets one_leg/movie_man_9 prompt control; source49@8fps and generated0,3,...144; visual task/time checks recorded separately")
ast.parse(score);(P/'scripts/score_one.py').write_text(score)
# Scientific source is pinned byte-for-byte; manifests and administrative wrappers are newly bound.
numeric=read(R/'configs/NUMERIC_INHERITANCE.json');assert all(sha(P/'runtime/official_metric'/n)==h for n,h in numeric['files'].items());save(P/'configs/NUMERIC_INHERITANCE.json',numeric)
save(P/'configs/RUNTIME.json',{'remote_root':DEST,'python':'/data3/researcher/ComfyUI/.venv/bin/python','GPU':'GPU-REDACTED','GPU_free_GiB':40,'case':'human/one_leg/000','methods':['reference','old_native','new_native'],'scientific_input_parent_sha256':sha(R/'prepared/MF_INPUTS.json'),'status':'CPU_READY_CONTROLLER_PENDING'})
print(json.dumps({'path':str(P),'numeric_files':len(numeric['files']),'GPU_started':False}))
