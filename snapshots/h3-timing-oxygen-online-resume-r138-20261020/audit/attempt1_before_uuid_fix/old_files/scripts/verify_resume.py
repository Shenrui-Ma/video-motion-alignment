"""Independent exact lineage check; recovered trajectory and spent work stay separate."""
from pathlib import Path
from observer_import import t,ROOT

def validate_source(root=ROOT):
 c=t.read_json(Path(root)/'configs/RESUME.json')
 for rel,row in c['source_files'].items():
  p=t.inside(str(Path(c['source_root'])/rel),c['source_root'])
  t.require(p.stat().st_size==row['bytes'] and t.sha(p)==row['sha256'],'resume source changed: '+rel)
 release=t.read_json(c['source_release'])
 t.require(release['passed'] and release['service_cleanup']['process_absent'] and
           release['service_cleanup']['own_compute_absent'] and
           release['observer_children']['all_exact_generations_absent'] and
           release['observer_children']['all_registered_CUDA_pids_absent'],'old generation release incomplete')
 old=t.read_json(c['source_audit'])
 t.require(old['status']=='failed' and len(old['counterfactual']['steps'])==9 and
           len(old['counterfactual']['branches'])==13,'old interrupted trajectory differs')
 return c,old

def check(audit,root=ROOT):
 import torch
 from H3X0Readout.core import tensor_signature
 cfg,old=validate_source(root);c=audit['counterfactual'];o=old['counterfactual'];r=c['resume']
 expected={'schema':'r138-resume-lineage-v1','config_sha256':t.sha(Path(root)/'configs/RESUME.json'),
           'source_run':cfg['source_run'],'source_audit':cfg['source_audit'],'source_release':cfg['source_release'],
           'start_physical_index':9,'inherited_complete_updates':9,'inherited_logical_model_nfe':12,
           'old_actual_executed_model_nfe':13,'reconstruction_model_nfe':0,
           'initial_rng_bytes_available':False,'replayed_archival_callbacks':list(range(9)),
           'first_restored_native_exact':True,'prefix_reconstruction_exact':True}
 t.require(all(r.get(k)==v for k,v in expected.items()),'resume lineage/evidence differs')
 t.require(c['seed']==o['seed'] and c['full_grid']==o['full_grid'] and c['initial_noise']==o['initial_noise']
           and c['conditioning']==o['conditioning'] and c['reference']==o['reference'],'resumed scientific state differs')
 t.require(r['new_initial_binding']==o['pair_gates'][0],'new initial input gate differs from old')
 t.require(c['measurements'][:9]==o['measurements'][:9],'inherited observations changed')
 for index,step in enumerate(c['steps']):
  expected_generation='R133' if index<9 else 'R138'
  t.require(step['execution_generation']==expected_generation,'step generation differs')
  if index<9:
   actual=dict(step);actual.pop('execution_generation');actual['chosen_file']=o['steps'][index]['chosen_file']
   t.require(actual==o['steps'][index],'inherited step/decision changed')
 oldb={(v['physical_index'],v['branch']):v for v in o['branches']}
 for row in c['branches']:
  inherited=row['physical_index']<9
  t.require(row['execution_generation']==('R133' if inherited else 'R138'),'branch generation differs')
  if inherited:
   actual=dict(row);actual.pop('execution_generation');actual['file']=actual.pop('original_file')
   t.require(actual==oldb[row['physical_index'],row['branch']],'inherited actual branch changed')
 new=[v for v in c['branches'] if v['physical_index']>=9]
 restored=[v for v in new if v['physical_index']==9 and v['branch']=='native']
 t.require(len(restored)==1 and r['discarded_old_execution']==oldb[9,'native'],'interrupted prediction accounting differs')
 for key in ('same_input','normalized_stream_signatures','raw_stream_signatures','sigma','sigma_next','seed','condition_sha256','reference_sha256'):
  t.require(restored[0][key]==oldb[9,'native'][key],'restored Native9 differs: '+key)
 state=torch.load(cfg['state_file'],map_location='cpu',weights_only=True)['packed']
 t.require(tensor_signature(state)==r['state9_signature']==restored[0]['same_input'],'state9 entity differs')
 t.require(r['actual_new_model_nfe']==len(new) and r['actual_new_euler_updates']==11 and
           r['logical_model_nfe']==c['logical_model_nfe']==len(c['branches']) and
           r['logical_euler_updates']==c['logical_euler_updates']==20 and
           r['actual_all_generations_model_nfe']==13+len(new)==len(c['branches'])+1,
           'logical/actual generation counters differ')
 inputs={v['physical_index']:v for v in c['inputs'] if v['physical_index']>=9}
 t.require(sorted(inputs)==list(range(9,20)),'new full-state checkpoints missing')
 from H3AutomaticWindowRouter.selector import Controller
 from H3AutomaticWindowRouter.geometry import Geometry
 case=t.read_json(Path(root)/'configs/protocol.json')['cases'][0];controller=Controller(Geometry.from_case(case),arm=case['arm'])
 for index in range(20):
  if index>=9:
   row=inputs[index];t.require(t.sha(row['file'])==row['file_sha256'],'checkpoint entity changed')
   payload=torch.load(row['file'],map_location='cpu',weights_only=True)
   t.require(tensor_signature(payload['packed'])==row['packed_signature']==next(v['same_input'] for v in new if v['physical_index']==index and v['branch']=='native'),'checkpoint input changed')
   memory=payload['controller_memory']
   t.require(memory['policy_previous']==controller.policy.previous and memory['policy_last_index']==controller.policy.last_index and memory['controller_last_index']==controller.last_index and memory['callback_count']==index,'checkpoint controller state differs')
   t.require(set(payload['rng_state'])=={'cpu','cuda'} and all(v.dtype==torch.uint8 and v.ndim==1 for v in payload['rng_state'].values()),'new RNG checkpoint absent')
  controller.select(index,c['measurements'][index])
 return dict(r,source_audit_sha256=t.sha(cfg['source_audit']),source_release_sha256=t.sha(cfg['source_release']),state_file_sha256=t.sha(cfg['state_file']),source_files=cfg['source_files'],verified_new_checkpoint_indices=list(range(9,20)))
