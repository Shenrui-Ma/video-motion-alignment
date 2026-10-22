"""Small CPU intake boundary for the actual R133 visible-only output."""
from pathlib import Path
import json,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
RUN='r133_short_0252_seed2026101703_visible_only'
def require(v,message):
 if not v:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def bound(p):return {'file':str(p),'sha256':sha(p)}
def config():return read(ROOT/'configs/FORMAL_CONTRACT.json')
def safe_path(path):
 p=Path(path);require(p.is_relative_to(config()['producer_remote']) and '..' not in p.parts,'outside actual producer');return p
def check_bindings(v):
 if isinstance(v,dict):
  if 'file' in v and 'sha256' in v:require(sha(v['file'])==v['sha256'],'historical binding changed: '+v['file'])
  for x in v.values():check_bindings(x)
 elif isinstance(v,list):
  for x in v:check_bindings(x)
def validate_static():
 c=config();f=read(ROOT/'FORMAL_CONSUMER_FREEZE.json');check_bindings(c['root_formal_review']);check_bindings(c['root_result_interpretation_plan'])
 for rel,h in f['files'].items():require(sha(ROOT/rel)==h,'consumer file changed: '+rel)
 p=Path(c['producer_local']);require(sha(p/'deploy_manifest.json')==c['producer_seal_sha256'],'producer seal differs')
 for rel,row in read(p/'deploy_manifest.json')['files'].items():require(sha(p/rel)==row['sha256'],'producer file changed: '+rel)
 for name in ('HISTORY_FREEZE.json','PRECHECK_BINDING_FREEZE.json'):require(sha(ROOT/name)==c['historical_freezes'][name],'historical freeze changed')
 h=read(ROOT/'configs/HISTORICAL_INPUTS.json');check_bindings(h);check_bindings(read(ROOT/'configs/PRECHECK_BINDING.json'))
 q=c['case'];require(q['run_id']==RUN and q['arm']=='visible_only' and q['valid_frame_count']==98 and q['geometry']=={'width':1312,'height':736,'frames':107,'fps':24},'single actual output/domain differs')
 require(q['video_sha256']==h['historical_roles']['source']['full_video']['sha256'],'historical source differs')
 require(read(ROOT/'configs/FORMAL_GRAPH.json')['5']['inputs']['prompt']==q['prompt'],'actual planned prompt differs')
 return c

def verify_counts(a):
 c=a['counterfactual'];mask=c['full_physical_indices'];k=len(mask);nfe=20+k
 require(a['status']=='complete' and mask==sorted(set(mask)) and all(type(i)is int and 1<=i<20 for i in mask),'invalid actual ON indices')
 require(c['actual_model_nfe']==nfe and c['actual_euler_updates']==c['callback_count']==20,'prediction/update count differs')
 require(a['completed_forward_calls']==nfe and a['completed_calls']==50*nfe and a['routed_calls']==50*k and a['calls_by_forward']==[50]*nfe,'actual layer counts differ')
 require(len(c['branches'])==nfe and len(c['steps'])==len(c['measurements'])==20,'incomplete online records')
 require([s['physical_index'] for s in c['steps']]==list(range(20)) and [s['physical_index'] for s in c['measurements']]==list(range(20)),'physical index coverage differs')
 require([b['nfe_index'] for b in c['branches']]==list(range(nfe)),'prediction index coverage differs')
 first=mask[0] if mask else None
 for s in c['steps']:require(s['decision']['chosen_full']==(s['physical_index'] in mask),'decision differs from actual mask')
 initial=[g for g in c['pair_gates'] if g['gate']=='initial_binding'];require(len(initial)==1 and initial[0]['pass']is True and initial[0]['actual_noise_and_producer_clean_inputs_exact']is True,'initial input/noise equality absent')
 prefix=[g for g in c['pair_gates'] if g['gate']=='native_prefix'];require([(g['physical_index'],g['branch']) for g in prefix]==[(b['physical_index'],b['branch']) for b in c['branches']],'prefix records incomplete')
 for g in prefix:
  eligible=g['branch']=='native' and (first is None or g['physical_index']<=first)
  require(g['status']==('pass' if eligible else 'not_applicable'),'historical equality applied outside common prefix')
  if eligible:require(g['tensor_equal']is True,'eligible actual prefix not equal')
 return {'active_indices':mask,'first_on':first,'NFE':nfe,'updates':20,'observations':20,'routed_blocks':50*k}

def verify_gate(g,started,complete,release,a):
 c=config();runtime=read(ROOT/'configs/FORMAL_RUNTIME.json');owner=started['service'];counts=verify_counts(a)
 require(g['schema']=='r86-online-runtime-gate-v1' and g['passed']is True and g['status']=='pass' and g['valid_frames']==98 and g['cleanup_verified']is True,'actual online gate incomplete/failed')
 require(g['producer_manifest_sha256']==c['producer_seal_sha256'] and g['protocol_sha256']==c['protocol_sha256']==started['protocol_sha256'],'producer/protocol differs')
 require(g['service_record']==release['service']==owner,'actual owner generation differs')
 require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'] and owner['identity']['uid']==runtime['uid'] and owner['identity']['start_ticks'],'runtime identity differs')
 require(c['producer_remote'] in (' '.join(owner['identity']['cmdline']) if isinstance(owner['identity']['cmdline'],list) else owner['identity']['cmdline']),'service command outside producer')
 require(complete['passed']is True and complete['run_id']==RUN and complete['no_followup_submission']is True,'completion missing')
 require(release['passed']is True and release['service_cleanup']['process_absent']is True and release['service_cleanup']['own_compute_absent']is True,'main service release incomplete')
 require(release['observer_children']['all_exact_generations_absent']is True and release['observer_children']['all_registered_CUDA_pids_absent']is True,'decoder child release incomplete')
 require(g['verified_runs']==[RUN] and len(g['cases'])==1,'extra or missing actual output')
 r=g['cases'][0];require(r['run']==RUN and r['arm']=='visible_only' and r['mask']==counts['active_indices'] and r['first_on']==counts['first_on'] and r['NFE']==counts['NFE'] and r['updates']==20 and r['observations']==20,'gate actual decisions differ')
 require(r['independent_parent_inputs']['actual_clean_inputs_equal']is True and r['independent_parent_inputs']['initial_video_audio_noise_equal']is True,'independent parent inputs failed')
 end=counts['first_on'] if counts['first_on'] is not None else 19;prefix=r['independent_native_prefix'];require([x['physical_index'] for x in prefix]==list(range(end+1)) and all(x['actual_video_audio_tensor_equal']is True for x in prefix),'independent eligible prefix incomplete')
 require([x['index'] for x in g['raw_filtered_pose_binding']]==list(range(20)) and [x['index'] for x in g['efficiency']['per_step']]==list(range(20)),'raw/filtered pose or timing coverage incomplete')
 require(g['efficiency']['NFE']==counts['NFE'],'efficiency NFE differs');safe_path(g['video']['file']);return counts

def verify_collection():
 validate_static();d=ROOT/'incoming/actual';m=read(d/'COLLECTION.json')
 for rel,h in m['files'].items():require(sha(d/rel)==h,'collected evidence changed: '+rel)
 g=read(d/'ONLINE_RUNTIME_GATE.json');complete=read(d/'COMPLETE_REVIEW_HOLD.json');require(complete['gate_sha256']==sha(d/'ONLINE_RUNTIME_GATE.json'),'completed gate SHA differs')
 counts=verify_gate(g,read(d/'STARTED.json'),complete,read(d/'ROOT_EXIT_RECEIPT.json'),read(d/'counterfactual.json'))
 require(sha(d/'visible_only.mp4')==g['video']['sha256'],'actual output changed')
 graph=read(d/'graph.json');history=read(d/'history.json');job=read(d/'job.json');owner=g['service_record']
 require(graph==read(ROOT/'configs/FORMAL_GRAPH.json') and graph['5']['inputs']['prompt']==config()['case']['prompt'],'actual graph/prompt differs')
 require(history['status']['completed']is True and history['status']['status_str']=='success' and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'actual Comfy history differs')
 require(job['status']=='success' and job['name']==RUN and job['graph_sha256']==sha(d/'graph.json') and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'actual job generation differs')
 e=history['outputs']['14']['images'];require(len(e)==1 and e[0]['type']=='output','unexpected actual media');require(str(Path(config()['producer_remote'])/'output'/e[0].get('subfolder','')/e[0]['filename'])==g['video']['file'],'history output identity differs')
 return m
