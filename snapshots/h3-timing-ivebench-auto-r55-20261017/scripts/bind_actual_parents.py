"""Bind all five actual R54 archives and finite source90 poses after root policy choice."""
import argparse,copy,hashlib,json,shutil,sys
from pathlib import Path
from intake_parent_metadata import inspect
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'h3-timing-ivebench-native-r54-20261017'
LEGACY=ROOT.parent/'h3-timing-auto-source28289-r45-20261017'
sys.path.insert(0,str(ROOT/'extensions'))
from H3AutomaticWindowRouter.geometry import Geometry
from pose_domain import validate_pose

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  if read(p)!=v:raise ValueError('different existing binding:'+str(p))
  return
 with p.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def copied(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():
  if dst.read_bytes()!=src.read_bytes():raise ValueError('different existing binding:'+str(dst))
 else:shutil.copyfile(src,dst)
 return str(dst.relative_to(ROOT))

def validate_sources(folder,cases):
 folder=Path(folder);protocol=read(folder/'PROTOCOL.json');p_sha=sha(folder/'PROTOCOL.json');rows={r['pair_id']:r for r in protocol['cases']};out={}
 if protocol['schema']!='r54-source-pose90-v1' or protocol['pose_script_sha256']!=sha(ROOT/'scripts/pose_probe.py'):raise ValueError('source pose implementation differs')
 if set(rows)!={c['source_id'] for c in cases}:raise ValueError('source pose five cases differ')
 for case in cases:
  source=case['source_id'];row=rows[source];complete=read(folder/('COMPLETE_'+source+'.json'))
  if complete['status']!='complete' or complete['protocol_sha256']!=p_sha or len(complete['cases'])!=1:raise ValueError('source pose incomplete:'+source)
  saved=complete['cases'][0];path=folder/'outputs'/(Path(case['video']).stem+'.pose.json')
  if row['video_sha256']!=case['video_sha256'] or row['provenance_sha256']!=case['provenance_sha256'] or row['effective_frames']!=case['valid_frame_count']:raise ValueError('source pose task binding differs')
  if saved['pair_id']!=source or sha(path)!=saved['pose_sha256'] or saved['video_sha256']!=case['video_sha256'] or saved['valid_indices']!=list(range(case['valid_frame_count'])) or saved['padding_indices']!=list(range(case['valid_frame_count'],90)):raise ValueError('source pose hash/domain differs')
  raw=validate_pose(path,Geometry.from_case(case));provenance=raw['provenance']
  if raw['video']['sha256']!=case['video_sha256'] or provenance['script_sha256']!=protocol['pose_script_sha256'] or provenance['device']!='cpu' or provenance['providers']!=['CPUExecutionProvider']:raise ValueError('source pose runtime differs')
  out[source]={'path':str(path),'sha256':sha(path),'completion':str(folder/('COMPLETE_'+source+'.json'))}
 return protocol,out

def main(archive,source_poses):
 archive=Path(archive);component=read(ROOT/'configs/protocol.json');selection=read(ROOT/'configs/POLICY_SELECTION.json')
 if (ROOT/'deploy_manifest.json').exists() or read(ROOT/'configs/PARENT_CLOSURE.json')['ready']:raise FileExistsError('already bound/sealed')
 if component['policy_choice']['status']!='FROZEN_BY_ROOT' or selection['status']!='FROZEN_BY_ROOT':raise ValueError('root must choose policy before parent binding')
 for rel,digest in selection['selected_files'].items():
  if sha(ROOT/rel)!=digest:raise ValueError('selected policy changed')
 intake=inspect(archive)
 if intake['status']!='INTAKE_RECORDED_NOT_BOUND' or any(r['missing_metadata'] for r in intake['cases']):raise ValueError('five actual R54 archives required')
 source_protocol,sources=validate_sources(source_poses,component['cases'])
 parent_runtime=archive/'configs/runtime.json'
 if sha(parent_runtime)!=read(archive/'deploy_manifest.json')['files']['configs/runtime.json']['sha256']:raise ValueError('actual R54 runtime configuration changed')
 # All prerequisites checked before replacing pending documents.
 copied(ROOT/'configs/protocol.json',ROOT/'audit/COMPONENT_PROTOCOL_before_bind.json')
 copied(ROOT/'configs/PARENT_CLOSURE.json',ROOT/'audit/PARENT_CLOSURE_before_bind.json')
 protocol=copy.deepcopy(read(LEGACY/'configs/protocol.json'))
 protocol.update(schema='r55-ivebench-five-paired-auto-v1',scope='Five original IVEBench editing tasks; all outcomes; automatic observer over each valid source prefix;90-frame model canvas.',cases=component['cases'],geometry=[1312,736,90,24],policy_choice=component['policy_choice'],resources=component['resources'],preparation_status='ACTUAL_R54_PARENTS_BOUND_ROOT_GPU_GATES_PENDING')
 protocol['resources'].update(threads=4,maximum_own_GPUs=2,job_timeout_seconds=14400,service_timeout_seconds=43200,idle_hold_seconds=1800)
 protocol['observer'].pop('source_pose_sha256',None);protocol['observer'].update(source_pose_binding='per-case local frozen source_pose_path/source_pose_sha256',valid_frame_count='per-case87/86/74/78/89',padding='excluded before scale, window scan, lag/null matching and common support',eligible_lag='same-sign abs(lag)>2' if selection['choice']=='signed_R53' else 'lag>2',persistence_direction='same direction' if selection['choice']=='signed_R53' else 'positive delayed only')
 protocol['actuator']['bin_boundary']='Complete positional bins; per-decision bin_coverage records any padding spillover'
 protocol['prefix'].update(all_OFF='Compare each actualR54 finalAV; encodedRGB assessed separately',availability='Actual five successfulR54 histories and21AV endpoints',historical_limit='Six actual clean-condition entities, exact noise,21Native endpoint files; no historical full processed-condition tree')
 protocol['evaluation']={'main':'IVEBench Motion Fidelity on each valid prefix after fixed crop16,8,1280,720','manual_window_used_online':False,'fixed_five_outcomes_retained':True,'source_score':'reuse byte-exact R54 source_score artifact','full_benchmark_reproduction':False}
 protocol['inherited_rule'].update(parent='R50 geometry-aware controller / root-selected existing policy',source_only_pose='per-case frozen source90',detector_policy_actuator_unchanged=True)
 closure={'schema':'r55-five-case-parent-closure-v1','ready':True,'status':'READY','final_archive_ready':True,'cases':{},'GPU':'root gates pending'}
 for case,evidence in zip(protocol['cases'],intake['cases']):
  source=case['source_id'];folder=ROOT/'configs/parents'/source;required=[]
  for field,key in {'parent_graph':'graph','parent_conditioning':'conditioning','parent_noise':'noise','parent_captures':'captures'}.items():case[field]=copied(Path(evidence['files'][key]['path']),folder/(key+'.json'));required.append(case[field])
  for key in ('history','job','router','shared'):required.append(copied(Path(evidence['files'][key]['path']),folder/(key+'.json')))
  for key in ('RUN_GATE.json','FILE_INVENTORY.json','RUNTIME_GATE.json','deploy_manifest.json'):required.append(copied(archive/key,folder/key))
  case['parent_file_inventory']=str((folder/'FILE_INVENTORY.json').relative_to(ROOT));source_record=sources[source]
  case['source_pose_path']=copied(Path(source_record['path']),folder/'source.pose.json');case['source_pose_sha256']=source_record['sha256'];required.append(case['source_pose_path'])
  required.append(copied(Path(source_record['completion']),folder/'source_pose_complete.json'))
  condition=read(ROOT/case['parent_conditioning']);closure['cases'][source]={'ready':True,'parent_run':case['parent_run'],'required_actual_files':required,'actual_file_sha256':{x:sha(ROOT/x) for x in required},'packed_layout':condition['packed_layout'],'source_pose_sha256':case['source_pose_sha256'],'tensor_inventory':evidence['tensor_inventory']}
 inputs={}
 for p in (archive/'inputs').iterdir():
  if p.is_file():copied(p,ROOT/'inputs'/p.name);inputs[p.name]=sha(p)
 put(ROOT/'configs/input_hashes.json',inputs)
 copied(parent_runtime,ROOT/'configs/parent_runtime.json')
 copied(Path(source_poses)/'PROTOCOL.json',ROOT/'configs/source_pose_protocol.json')
 (ROOT/'configs/protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n');(ROOT/'configs/PARENT_CLOSURE.json').write_text(json.dumps(closure,indent=2)+'\n')
 copied(ROOT/'configs/protocol.json',ROOT/'PROTOCOL.json');protocol_sha=sha(ROOT/'configs/protocol.json')
 p=ROOT/'extensions/H3AutomaticWindowRouter/transport.py';text=p.read_text();old="PROTOCOL_SHA='UNSEALED_R55_PARENT_AND_POLICY_PENDING'"
 if old not in text:raise ValueError('protocol placeholder changed')
 p.write_text(text.replace(old,'PROTOCOL_SHA='+repr(protocol_sha)))
 science=copy.deepcopy(read(PARENT/'configs/scientific_contract.json'));science.update(schema='r55-ivebench-five-auto-v1',cases=protocol['cases'],arms=['auto'],case_order=[c['run_id'] for c in protocol['cases']],NFE_per_job='20+K',blocks_per_job='50*(20+K)',routed_blocks_per_job='50*K',router=protocol['actuator'])
 science['continuous']['job_timeout_seconds']=14400;put(ROOT/'configs/scientific_contract.json',science)
 runtime=read(ROOT/'configs/runtime.json');runtime['status']='READY';(ROOT/'configs/runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
 put(ROOT/'FREEZE.json',{'schema':'r55-production-freeze-v1','files':{'PROTOCOL.json':protocol_sha,'configs/protocol.json':protocol_sha,'configs/POLICY_SELECTION.json':sha(ROOT/'configs/POLICY_SELECTION.json')}})
 bindings={'schema':'r55-host41-observer-bindings-v1','aux_root':'/data3/researcher/ComfyUI-H3/custom_nodes/comfyui_controlnet_aux','vae':runtime['models']+'/vae/minimax_h3_video_vae_fp16.safetensors','vae_sha256':'7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522','comfy':runtime['core'],'runtime_deps':runtime['dependencies']}
 bindings['external_files']={bindings['aux_root']+'/'+rel:digest for rel,digest in source_protocol['aux_files'].items()}
 bindings['local_files']={str(p.relative_to(ROOT)):sha(p) for folder in ('scripts','configs','extensions') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name not in ('observer_bindings.json','admission.json','queue.json','runtime_provenance.json')}
 put(ROOT/'configs/observer_bindings.json',bindings);put(ROOT/'audit/ACTUAL_PARENT_INTAKE.json',intake)
 print(json.dumps({'bound_cases':5,'protocol_sha256':protocol_sha,'production_GPU_gates':'pending root'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--source-poses',type=Path,required=True);a=p.parse_args();main(a.archive,a.source_poses)
