"""Actual two-arm integrity, strict common prefix/banks, historical Native provenance."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from r115_contract import read,sha,require,registry,SHAPES,RUNS,ARMS,SEED,PAIR_ID,SHARED_ID,VALID
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature
from parent_evidence import comparable_conditions
from execution_gate import atomic,verify_seal
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


def verify_banks(root,run,router):
 sys.path.insert(0,str(root/'extensions'))
 from H3TemporalRouter.correspondence import FrozenBank,canonical
 import hashlib
 collection={};files=[];metadata=[]
 captures=router['correspondence_bank_captures'];require(len(captures)==50 and sorted(x['block'] for x in captures)==list(range(50)),'50 bank captures required')
 for block in range(50):
  folder=root/'audit/correspondence_banks'/run/f'block_{block:02d}';bank=FrozenBank.load(folder);record=bank.verify()
  require(bank.metadata['block']==block and bank.metadata['source_step']==5 and bank.metadata['spatial_grid']==[23,41],'bank provenance differs')
  require(bank.metadata['geometry']=={'batch':1,'heads':56,'total_bins':47,'valid_bins':43,'frame_rows':943,'head_dim':128},'bank geometry differs')
  capture=next(x for x in captures if x['block']==block)
  require(capture['bank_sha256']==record['bank_sha256'] and capture['matching_cuda_synchronized'] is True and capture['matching_cuda_seconds']>=0,'bank hash or synchronized timing differs')
  collection[str(block)]=record['bank_sha256'];metadata.append({'block':block,**record})
  for name in ('bank.json','indices.npz'):
   file=folder/name;files.append({'file':str(file),'sha256':sha(file),'bytes':file.stat().st_size})
 digest=hashlib.sha256(canonical(collection)).hexdigest()
 require(router['correspondence_bank_collection']['blocks']==collection and router['correspondence_bank_collection']['collection_sha256']==digest,'frozen collection receipt differs')
 return {'passed':True,'capture_step':5,'collection_sha256':digest,'blocks':metadata,'files':files,'total_matching_cuda_seconds':sum(x['matching_cuda_seconds'] for x in captures),
         'coordinate_mapping':{'grid_hw':[23,41],'reference_geometry_wh':[1312,736],'token_center_xy':'(32*(s%41)+16,32*(s//41)+16)','evaluation_crop_xywh':[16,8,1280,720],'temporal_position_bin_sizes':'repeat [1,4,4,4,4], first43valid; position coverage only, not VAE receptive field'}}

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for x in value.values():yield from walk_blobs(x)
 elif isinstance(value,list):
  for x in value:yield from walk_blobs(x)

def compare_initial_noise(root,records):
 saved=torch.load(root/'audit'/(PAIR_ID+'_noise.pt'),map_location='cpu',weights_only=True)
 require(saved['signature']=={'seed':SEED,'nested':True,'shapes':[list(SHAPES[k]) for k in ('video','audio')],'dtypes':['torch.float32','torch.float32'],'batch_index':None},'initial noise seed/signature changed')
 actual=[{k:signature(x)[k] for k in ('shape','dtype','sha256')} for x in saved['tensors']]
 require(actual==saved['hashes'] and [list(x.shape) for x in saved['tensors']]==[list(SHAPES[k]) for k in ('video','audio')],'actual initial noise hash/geometry changed')
 for run,n in zip(RUNS,records):
  require(n['run_id']==run and n['pair_id']==PAIR_ID and n['signature']==saved['signature'] and n['actual_noise_streams']==actual,'new arms do not share initial AV noise')
 return {'file':str(root/'audit'/(PAIR_ID+'_noise.pt')),'sha256':sha(root/'audit'/(PAIR_ID+'_noise.pt')),'signature':saved['signature'],'actual_noise_streams':actual}

def expected_config(root,run,arm):
 remote=Path(read(root/'configs/runtime.json')['remote_root']);m=str(remote/'audit/x0'/run/'manifest.json')
 conf={'root':str(remote/'audit/correspondence_banks'/run),'valid_bins':43,'spatial_grid':[23,41],'prefix_manifest':m,'paired_prefix_manifest':m}
 if arm=='matched_one_bin':conf.update(paired_root=str(remote/'audit/correspondence_banks'/RUNS[0]),paired_prefix_manifest=str(remote/'audit/x0'/RUNS[0]/'manifest.json'))
 return conf

def verify_pair(root=ROOT):
 root=Path(root);torch.set_num_threads(1);verify_seal(root);jobs,order=registry(root);rt=read(root/'configs/runtime.json');owner=read(root/'processes/service.json')
 require(owner['gpu_uuid']==rt['gpu_uuid'] and owner['port']==rt['port'] and owner['identity']['uid']==rt['uid'] and str(root/'scripts/service_entry.py') in owner['identity']['cmdline'],'actual owner runtime changed')
 results={};manifests=[];conditions=[];noises=[];bank_proofs={};checks={'producer_seal':True,'same_service_runtime':True};shared=root/'audit'/(SHARED_ID+'_conditioning.json');shared_record=read(shared)
 blobs=[];seen=set()
 for record in walk_blobs(shared_record):
  if record['tensor_file'] not in seen:seen.add(record['tensor_file']);blobs.append(inspect_blob(root/'audit',record))
 require(len(blobs)==6,'six reference-only condition tensors required')
 for run,arm in zip(RUNS,ARMS):
  row=jobs[run];g=read(root/'configs/graphs'/(run+'.json'));grid=torch.tensor([float(x) for x in g['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
  hist=read(root/'logs'/(run+'_history.json'));job=read(root/'logs'/(run+'_job.json'))
  require(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==g and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run,'actual run/history changed')
  require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'],'actual generation differs')
  c=read(root/'audit'/(run+'_conditioning.json'));conditions.append(c);require(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']==SHARED_ID and c['pair_snapshot']['source_manifest']==shared.name and c['pair_snapshot']['source_manifest_sha256']==sha(shared) and c['prompt']==row['case']['prompt'],'actual condition shared provenance changed')
  proof=read(root/'audit'/(run+'_parent_condition_match.json'));require(proof['passed'] is True and proof['stage']=='before_DiT' and proof['current_run']==run and proof['comparison']==('self_integrity' if arm==ARMS[0] else 'two_new_arms_exact'),'pre-DiT proof changed')
  require(len(condition_files(c))==6,'six conditions required')
  router=read(root/'audit/router'/(run+'.json'))
  expected={'run_id':run,'mode':arm,'alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,144],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
  require(all(router.get(k)==v for k,v in expected.items()),'router actual count/parameters differ')
  plan=router['validated_layout'];require(plan['frame_rows']==943 and plan['latent_interval_half_open']==[0,43] and plan['pixel_interval_inclusive']==[0,144] and plan['position_bin_coverage_inclusive']==[0,144] and plan['reference_image_segments']==[],'valid reference domain differs')
  require(all(x.get('sampled_finite',True) for x in router['forward_summaries']),'nonfinite routed output')
  require(router['correspondence_config']==expected_config(root,run,arm),'runtime bank/prefix binding changed')
  require(router['correspondence_prefix_gate']['passed'] is True and router['correspondence_prefix_gate']['prefix_steps']==list(range(6)),'before-intervention prefix file gate failed')
  m,files,_=inspect_capture(root/'audit/x0'/run,run,grid,SEED,row['case']);manifests.append(m);noises.append(read(root/'audit'/(run+'_noise.json')))
  bank=verify_banks(root,run,router);bank_proofs[run]=bank
  video=output_file(root,hist);props=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(video)],capture_output=True,text=True,timeout=120,check=True).stdout)['streams'];require(len(props)==1,'one stream required');v=props[0]
  require(v['width']==1312 and v['height']==736 and v['avg_frame_rate']=='24/1' and int(v['nb_read_frames'])==158,'video geometry changed')
  results[arm]={'run_id':run,'video':{'file':str(video),'sha256':sha(video),'properties':v},'valid_frames':145,'NFE':20,'Euler_updates':20,'routed_blocks':450,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'snapshots':files,'prefix_scope':'self_file_integrity' if arm==ARMS[0] else 'equal_to_first_new_arm','router_file_sha256':sha(root/'audit/router'/(run+'.json')),'history_sha256':sha(root/'logs'/(run+'_history.json')),'job_sha256':sha(root/'logs'/(run+'_job.json'))}
  checks[arm+'_actual_execution']=True
 noise=compare_initial_noise(root,noises)
 checks['same_six_condition_tensors']=comparable_conditions(*conditions)
 checks['same_initial_noise_and_sigma_grid']=manifests[0]['noise']==manifests[1]['noise'] and manifests[0]['sigmas_video']==manifests[1]['sigmas_video'] and [c['sigma_audio'] for c in manifests[0]['captures']]==[c['sigma_audio'] for c in manifests[1]['captures']]
 prefix=compare_prefix(root/'audit/x0'/RUNS[0],manifests[0],RUNS[0],root/'audit/x0'/RUNS[1],manifests[1],RUNS[1])
 checks['two_new_arms_AV_prefix_0_5_bitwise_equal']=all(x[k] for x in prefix for k in ('video','audio'))
 checks['paired_all50_bank_metadata_indices_mask']=bank_proofs[RUNS[0]]['blocks']==bank_proofs[RUNS[1]]['blocks']
 checks['paired_bank_collection']=bank_proofs[RUNS[0]]['collection_sha256']==bank_proofs[RUNS[1]]['collection_sha256']
 historical=read(root/'design/HISTORICAL_NATIVE.json');native=copy.deepcopy(historical['run']);native['historical_parent']=True;native['same_host_strict_comparison']=False
 results={'native':native,**results}
 return {'schema':'r115-two-new-arm-runtime-gate-v1','passed':all(checks.values()),'checks':checks,'source_id':'long_0174','runs':results,'new_run_ids':list(RUNS),'service_owner':owner,'runtime_profile':rt,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'producer_seal_sha256':sha(root/'deploy_manifest.json'),'historical_native':historical,'historical_native_gate_sha256':sha(root/'design/HISTORICAL_NATIVE_GATE.json'),'historical_cross_host_prefix_equality_required':False,'condition_tensor_files':blobs,'initial_noise':noise,'banks':bank_proofs,'paired_bank_collection_sha256':bank_proofs[RUNS[0]]['collection_sha256'],'prefix_tensor_comparison':prefix,'first_allowed_prediction_divergence_index':6,'valid_frames':145,'total_frames':158,'fps':24,'evaluation_crop_xywh':[16,8,1280,720],'created_unix':time.time()}

if __name__=='__main__':
 dest=ROOT/'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json'
 try:
  value=verify_pair();atomic(dest,value);require(value['passed'],'two-arm actual checks failed')
 except BaseException as e:atomic(dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json'),{'passed':False,'error':repr(e),'unix':time.time()});raise
 print(json.dumps({'file':str(dest),'sha256':sha(dest),'passed':True,'checks':value['checks']},indent=2))
