"""Bounded CPU contract and online-accounting checks, not simulated experiment results."""
import ast,copy,sys
from common import *
def fixture(mask):
 branches=[];prefix=[]
 for i in range(20):
  for branch in ('native','full') if i in mask else ('native',):
   branches.append({'physical_index':i,'branch':branch,'nfe_index':len(branches)})
   eligible=branch=='native' and (not mask or i<=mask[0]);prefix.append({'gate':'native_prefix','physical_index':i,'branch':branch,'status':'pass' if eligible else 'not_applicable','tensor_equal':eligible})
 n=20+len(mask)
 return {'status':'complete','completed_forward_calls':n,'completed_calls':50*n,'routed_calls':50*len(mask),'calls_by_forward':[50]*n,'counterfactual':{'full_physical_indices':mask,'actual_model_nfe':n,'actual_euler_updates':20,'callback_count':20,'branches':branches,'steps':[{'physical_index':i,'decision':{'chosen_full':i in mask}} for i in range(20)],'measurements':[{'physical_index':i} for i in range(20)],'pair_gates':[{'gate':'initial_binding','pass':True,'actual_noise_and_producer_clean_inputs_exact':True}]+prefix}}
def check():
 c=validate_static();plan=read(ROOT/'configs/EVALUATION_PLAN.json');require(len(plan['events'])==3 and len(plan['phase_pairs'])==2 and plan['valid_frames']==98,'evaluation plan differs')
 for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text())
 import remote,render_pair,full_frame_review,consume_online
 require(remote.SSH[-1]=='H3_SERVER_B','wrong host transport')
 tests=[]
 for mask in ([],[1],[1,2,9,19]):require(verify_counts(fixture(mask))['NFE']==20+len(mask),'valid accounting rejected');tests.append({'control':mask,'passed':True})
 mutations=[('missing_observation',lambda a:a['counterfactual']['measurements'].pop()),('extra_update',lambda a:a['counterfactual'].__setitem__('actual_euler_updates',21)),('wrong_routed_blocks',lambda a:a.__setitem__('routed_calls',0)),('late_historical_equality',lambda a:a['counterfactual']['pair_gates'][-1].__setitem__('status','pass')),('unregistered_ON_zero',lambda a:a['counterfactual'].__setitem__('full_physical_indices',[0])),('missing_input_equality',lambda a:a['counterfactual']['pair_gates'][0].__setitem__('actual_noise_and_producer_clean_inputs_exact',False))]
 for label,mutate in mutations:
  a=fixture([1]);mutate(a)
  try:verify_counts(a)
  except ValueError:tests.append({'rejected_mutation':label,'passed':True})
  else:raise AssertionError(label+' was accepted')
 require('torch' not in sys.modules,'CPU consumer imported model runtime')
 return {'passed':True,'producer_seal_sha256':c['producer_seal_sha256'],'producer_files':len(read(Path(c['producer_local'])/'deploy_manifest.json')['files']),'frozen_files':len(read(ROOT/'FORMAL_CONSUMER_FREEZE.json')['files']),'controls':tests,'shared_helpers_imported':True,'host':remote.SSH[-1],'actual_output_available':(ROOT/'incoming/actual/COLLECTION.json').exists(),'new_GPU_entry':False,'no_tensor_payload_transfer':True,'history_MF_reuse_only':True}
if __name__=='__main__':
 r=check();save(ROOT/'audit/FORMAL_CPU_CHECK.json',r);print(json.dumps(r,ensure_ascii=False))
