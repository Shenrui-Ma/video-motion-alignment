"""CPU evidence gate for actual same-host historical Native and new fixed guidance."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature
from r107_contract import read,sha,require,validate_job,SHAPES,SOURCES,VALID,run_id,routing_layout
from parent_evidence import verify_parent,comparable_conditions
from execution_gate import atomic

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)
def output_file(root,hist):
 images=hist['outputs']['14']['images'];require(len(images)==1,'expected one output video');r=images[0]
 require(r.get('type')=='output','wrong output type');rel=Path(r.get('subfolder',''))/r['filename']
 require(not rel.is_absolute() and '..' not in rel.parts,'unsafe output path');p=root/'output'/rel
 require(p.is_file() and not p.is_symlink(),'output absent');return p

def compare_prefix(current_folder,current_manifest,current_run,parent_folder,parent_manifest,parent_run,shapes=SHAPES):
 results=[]
 for i in range(6):
  a,af=checked_snapshot(current_folder,current_manifest['captures'][i],current_run,shapes)
  b,bf=checked_snapshot(parent_folder,parent_manifest['captures'][i],parent_run,shapes)
  require(a['metadata']['step_zero_based']==b['metadata']['step_zero_based']==i and a['metadata']['model_call_one_based']==b['metadata']['model_call_one_based']==i+1,'prefix prediction index mismatch')
  results.append({'step_zero_based':i,'model_call_one_based':i+1,'video':torch.equal(a['video'],b['video']),'audio':torch.equal(a['audio'],b['audio']),'current_file_sha256':af['sha256'],'parent_file_sha256':bf['sha256']})
 return results

def verify(source,root=ROOT):
 root=Path(root).resolve();torch.set_num_threads(1);run=run_id(source);row=validate_job(run,root);case=row['case'];b=read(root/'configs/parent_bindings.json')[source];prior=Path(b['producer_remote']);oldrun=b['run_id']
 parent_proof=verify_parent(root,source,include_snapshots=True);parent_gate=read(root/'design'/source/'PARENT_ACTUAL_GATE.json');oldarm='p1' if source=='short_0210' else 'native'
 checks={};runtime=read(root/'configs/runtime.json');seal=read(root/'deploy_manifest.json');checks['producer_seal']=all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
 runtime_keys=('host','core','python','dependencies','models','kj_nodes','reserve_vram','memory_mode')
 checks['same_host_numerical_runtime']=all(runtime[k]==b['runtime'][k] for k in runtime_keys)
 owner=read(root/'processes/service.json');checks['actual_runtime_device']=owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port']
 graph=read(root/'configs/graphs'/(run+'.json'));grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 hist=read(root/'logs'/(run+'_history.json'));job=read(root/'logs'/(run+'_job.json'))
 checks['actual_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
 checks['actual_service_generation']=(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
 c=read(root/'audit'/(run+'_conditioning.json'));oldc=read(prior/'audit'/(oldrun+'_conditioning.json'));shared_name='r107_'+source+'_shared';shared=root/'audit'/(shared_name+'_conditioning.json')
 checks['actual_condition_snapshot']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==shared_name and c['pair_snapshot']['source_manifest']==shared.name and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==case['prompt'])
 checks['all_conditions_equal_actual_Native']=comparable_conditions(c,oldc)
 proof=read(root/'audit'/(run+'_parent_condition_match.json'));checks['pre_DiT_condition_gate']=(proof['passed'] is True and proof['stage']=='before_DiT' and proof['source_id']==source and proof['current_run']==run)
 require(len(condition_files(c))==6,'expected six condition blobs');blob_files=[];seen=set()
 for record in walk_blobs(read(shared)):
  if record['tensor_file'] not in seen:seen.add(record['tensor_file']);blob_files.append(inspect_blob(root/'audit',record))
 parent_blobs=[]
 for record in walk_blobs(oldc):
  if record.get('tensor_file') and record['tensor_file'] not in {x.get('relative') for x in parent_blobs}:
   checked=inspect_blob(prior/'audit',record);checked['relative']=record['tensor_file'];parent_blobs.append(checked)
 checks['actual_parent_six_condition_tensors']=(len(parent_blobs)==6 and all(x['sha256']==next(z['gate_file_sha256'] for z in b['condition_tensors'] if z['file']==x['file']) for x in parent_blobs))
 router=read(root/'audit/router'/(run+'.json'))
 expect={'run_id':run,'mode':'mass_preserve','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,VALID[source]-1],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
 checks['actual20NFE20Euler450routes']=all(router.get(k)==v for k,v in expect.items())
 plan=router['validated_layout'];route=routing_layout(case)
 checks['valid_physical_support']=(plan['frame_rows']==943 and plan['latent_interval_half_open']==route['latent_interval_half_open'] and plan['position_bin_coverage_inclusive']==route['position_bin_coverage_inclusive'] and plan['pixel_interval_inclusive']==[0,VALID[source]-1] and plan['reference_image_segments']==[])
 checks['sampled_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
 manifest,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,row['seed'],case);del prefix
 oldmanifest=read(prior/'audit/x0'/oldrun/'manifest.json');checks['same_sampler_grid_and_initial_packed_noise']=(manifest['noise']==oldmanifest['noise'] and manifest['sigmas_video']==oldmanifest['sigmas_video'] and [c['sigma_audio'] for c in manifest['captures']]==[c['sigma_audio'] for c in oldmanifest['captures']])
 comparisons=compare_prefix(root/'audit/x0'/run,manifest,run,prior/'audit/x0'/oldrun,oldmanifest,oldrun)
 checks['AV_prediction_prefix_0_5_bitwise_equal']=all(r[k] for r in comparisons for k in ('video','audio'))
 n=read(root/'audit'/(run+'_noise.json'));oldn=b['noise'];noise=root/b['new_noise_relative'];saved=torch.load(noise,map_location='cpu',weights_only=True)
 actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 checks['actual_raw_AV_noise_equal_Native']=(sha(noise)==oldn['current_file']['sha256'] and n['run_id']==run and n['pair_id']=='r107_'+source+'_seed2026101701' and saved['signature']==n['signature']==oldn['signature'] and actual==saved['hashes']==n['actual_noise_streams']==oldn['actual_noise_streams'] and [list(t.shape) for t in saved['tensors']]==[list(SHAPES[k]) for k in ('video','audio')]);del saved
 video=output_file(root,hist);v=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(video)],capture_output=True,text=True,timeout=120,check=True).stdout)['streams'];require(len(v)==1,'one video required');v=v[0]
 checks['output_geometry']=(v['width']==1312 and v['height']==736 and v['avg_frame_rate']=='24/1' and int(v['nb_read_frames'])==158)
 native={'run_id':oldrun,'parent_root':str(prior),'video':copy.deepcopy(parent_gate['runs'][oldarm]['video']),'valid_frames':VALID[source],'NFE':20,'Euler_updates':20,'routed_blocks':0,'historical_parent':True}
 forced={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':v},'valid_frames':VALID[source],'NFE':20,'Euler_updates':20,'routed_blocks':450,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds':sum(x['capture_seconds'] for x in manifest['captures']),'snapshots':files}
 return {'schema':'r107-historical-native-paired-runtime-gate-v1','passed':all(checks.values()),'checks':checks,'source_id':source,'prompt_version':'actual-parent-P1-verbatim','parent_evidence':parent_proof,'service_owner':owner,'runtime_profile':runtime,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'runs':{'native':native,'forced':forced},'valid_frames':VALID[source],'total_frames':158,'fps':24,'evaluation_crop_xywh':[16,8,1280,720],'condition_tensor_files':blob_files,'parent_condition_tensor_files':parent_blobs,'prefix_tensor_comparison':comparisons,'first_allowed_prediction_divergence_index':6,'created_unix':time.time()}

def persist_result(dest,result):
 # Re-verification of unchanged evidence preserves the established consumer binding.
 if dest.exists():
  old=read(dest)
  if {k:v for k,v in old.items() if k!='created_unix'}=={k:v for k,v in result.items() if k!='created_unix'}:return old
 atomic(dest,result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();dest=a.root/'analysis/postrun'/a.source/'PAIR_RUNTIME_GATE.json'
 try:result=verify(a.source,a.root)
 except BaseException as e:atomic(dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(e),'unix':time.time()});raise
 result=persist_result(dest,result);print(json.dumps({'receipt':str(dest),'sha256':sha(dest),'passed':result['passed'],'checks':result['checks']},indent=2))
 if not result['passed']:raise SystemExit(2)
