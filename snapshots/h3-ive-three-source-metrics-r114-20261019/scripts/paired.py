"""Actual paired evidence, kept separate from the earlier Native preview."""
from common import *

PAIR_CHECKS=REQUIRED_CHECKS+tuple(x.replace('native_','forced_',1) for x in REQUIRED_CHECKS if x.startswith('native_'))+('actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal')

def verify_pair_gate(g,source,owner):
 c=config();p=info(source)
 require(g.get('schema')=='r114-paired-runtime-gate-v1' and g.get('passed') is True,'paired gate not passed')
 require(g.get('source_id')==source and g.get('prompt_version')==p['prompt_version'],'source/prompt differs')
 require(set(g.get('runs',{}))=={'native','forced'},'actual Native and guided runs required')
 checks=g.get('checks');require(isinstance(checks,dict) and all(x is True for x in checks.values()),'failed actual paired check')
 require(all(checks.get(x) is True for x in PAIR_CHECKS),'required paired check missing')
 require(g.get('runtime_profile_sha256')==c['producer_runtime_sha256'] and g.get('runtime_profile')==read(ROOT/'configs/producer_runtime.json'),'runtime differs')
 require(g.get('service_owner')=={'pid':owner['pid'],'identity':owner['identity']},'paired service generation differs')
 for mode in ('native','forced'):verify_run(g['runs'][mode],p,mode)
 prefix=g.get('prefix_tensor_comparison',[])
 require(len(prefix)==6 and [x.get('step_zero_based') for x in prefix]==list(range(6)),'six actual prefix steps required')
 require(all(x.get(k) is True for x in prefix for k in ('video','audio')),'actual prefix tensor difference')
 require(g['runs']['native']['video']['file']!=g['runs']['forced']['video']['file'],'paired output files must differ')
 return g

def require_same_native(source,g):
 """If a preview was already collected, the pair must use that actual Native."""
 dest=ROOT/'incoming'/source
 if not dest.exists():return
 earlier=verify_intake(source)['runs']['native'];actual=g['runs']['native']
 for key in ('run_id','video','history_sha256','job_sha256','binding_artifacts'):
  require(earlier[key]==actual[key],'pair Native differs from collected preview: '+key)

def verify_pair_intake(source):
 dest=ROOT/'incoming_pairs'/source;receipt=read(dest/'COLLECTION.json');binding=read(ROOT/'audit/EXECUTION_BINDING.json')
 require(receipt['source_id']==source and receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'paired intake binding changed')
 for name,digest in receipt['files'].items():
  require(Path(name).name==name,'unsafe paired intake path');require(sha(dest/name)==digest,'paired intake file changed')
 g=verify_pair_gate(read(dest/'PAIR_RUNTIME_GATE.json'),source,binding['owner'])
 for mode in ('native','forced'):verify_small_evidence(dest,source,binding['owner'],g,mode)
 require_same_native(source,g)
 return g
