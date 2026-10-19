"""Bind verified R90 prompt-control media to unchanged official FlexiAct MF code; CPU only."""
from pathlib import Path
import hashlib,json,shutil,importlib.util,sys,copy
R=Path(__file__).resolve().parents[1];OLD=R.parent/'h3-flexiact-character-repair-mf-r98-20261019';M=R/'runtime/official_metric';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
prepared=read(R/'prepared/MF_INPUTS.json');assert sha(R/'prepared/MF_INPUTS.json')=='8710b5d68447e8b7d59eb1314a645a1297e533121e556bb81889d6d02dd85069'
assert not M.exists();shutil.copytree(OLD/'runtime/official_metric',M,ignore=shutil.ignore_patterns('inputs','SOURCE_INPUTS.json','__pycache__'))
inherit={str(p.relative_to(M)):sha(p) for p in sorted(M.rglob('*')) if p.is_file()}
assert all(sha(OLD/'runtime/official_metric'/n)==h for n,h in inherit.items())
case='human/one_leg/000';source=prepared['source_original'];assert sha(source['file'])==source['sha256']
ref={'id':case,'role':'reference','file':source['file'],'sha256':source['sha256'],'frames':49,'pts_seconds':[i/8 for i in range(49)],'original_frame_indices':list(range(49)),'original_fps':8,'official_source_url':read(R/'inputs/source_provenance.json')['official_source']['pinned_url'],'id_scope':'canonical motion-source identity; actual image pair one_leg/movie_man_9'}
save(M/'SOURCE_INPUTS.json',{'schema':'r90-official-flex-motion-source-v1','inputs':[ref]})
for role,row in prepared['targets'].items():
 for name in ['file','mapping','full']:assert Path(row[name]).is_file()
 assert sha(row['file'])==row['sha256'] and sha(row['mapping'])==row['mapping_sha256'] and sha(row['full'])==row['full_sha256']
 gate=R/'inputs'/('P0_GATE.json' if role=='old_native' else 'P1_GATE.json');g=read(gate);run=(g['runs']['native']['run_id'] if role=='old_native' else g['run_id'])
 meta={'run_id':run,'method':role,'comparison_kind':'prompt_control','official_pair_id':case,'edited49':row['file'],'edited49_sha256':row['sha256'],'full158_output':row['full'],'full158_output_sha256':row['full_sha256'],'full_output_indices':list(range(0,147,3)),'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,'original_source_sha256':source['sha256'],'producer_receipt':{'file':str(gate),'sha256':sha(gate)}}
 mp=R/'prepared'/role/'METRIC_INPUTS.json';save(mp,meta)
 item={'id':case,'role':'generated','file':row['file'],'sha256':row['sha256'],'frames':49,'pts_seconds':[i/8 for i in range(49)],'generation_frame_indices':list(range(0,147,3)),'generation_binding':{'metric_inputs':{'file':str(mp),'sha256':sha(mp)},'release_mapping':{'file':row['mapping'],'sha256':row['mapping_sha256']}}}
 save(R/'prepared'/role/'TRACK_INPUTS.json',{'schema':'r90-generated-flex-track-input-v1','inputs':[item]})
save(R/'configs/NUMERIC_INHERITANCE.json',{'source_runtime':str(OLD/'runtime/official_metric'),'files':inherit,'official_commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','checkpoint_sha256':prepared['checkpoint_required_sha256'],'comparison_kind':'prompt_control','guidance_used':False})
spec=importlib.util.spec_from_file_location('frozen_flex_runner',M/'run_tracks.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
checks=[]
for role in ['reference','old_native','new_native']:
 manifest=M/'SOURCE_INPUTS.json' if role=='reference' else R/'prepared'/role/'TRACK_INPUTS.json';item=read(manifest)['inputs'][0];assert sha(item['file'])==item['sha256'];module.check_timebase(Path(item['file']));checks.append(role+'_49_original_timestamps')
 if role!='reference':
  module.validate_generated_binding(item,Path(item['file']));checks.append(role+'_actual_generation_binding')
  wrong=copy.deepcopy(item);wrong['id']='human/incorrect/000'
  try:module.validate_generated_binding(wrong,Path(wrong['file']))
  except ValueError:checks.append(role+'_wrong_pair_rejected')
  else:raise AssertionError('incorrect pair accepted')
assert 'torch' not in sys.modules
save(R/'audit/OFFICIAL_BINDING_CPU_CHECK.json',{'passed':True,'checks':checks,'frozen_numeric_files':len(inherit),'runtime_source':str(OLD/'runtime/official_metric'),'GPU_started':False,'deployment_status':'LOCAL_CPU_READY; requires separate path relocation and host seal before GPU execution'})
print(json.dumps({'passed':True,'checks':len(checks),'numeric_files':len(inherit),'receipt_sha256':sha(R/'audit/OFFICIAL_BINDING_CPU_CHECK.json'),'GPU_started':False}))
