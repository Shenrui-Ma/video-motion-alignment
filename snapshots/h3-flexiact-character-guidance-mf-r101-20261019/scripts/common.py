from pathlib import Path
import json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[1];METRIC=ROOT/'runtime/official_metric';INDICES=list(range(0,147,3));CASE='human/human2animal_1/000'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def verify_runtime():
 j=read(ROOT/'CONSUMER_FREEZE.json')
 for name,digest in j['files'].items():require(sha(ROOT/name)==digest,'static input/code changed: '+name)
 return j

def validate_cache():
 import math
 u=read(ROOT/'configs/CACHE_REUSE.json');c=read(ROOT/'configs/r101_consumer_contract.json')
 for n,h in u['files'].items():require(sha(ROOT/'cache'/n)==h,'cache evidence changed: '+n)
 require(c['media']['source']['sha256']==u['source_prepared_sha256'] and c['media']['native']['sha256']==u['native_full_sha256'],'R101 media differs from cached source/Native')
 old=read(ROOT/'cache/R98_original_consumer_contract.json');require(old['media']['source']['sha256']==u['source_prepared_sha256'] and old['valid_frames']==147 and old['original_indices']==INDICES,'original prepared source provenance differs')
 expected={'checkpoint_sha256':'dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3','metric_functions_sha256':sha(METRIC/'METRIC_FUNCTIONS.json'),'vendor_manifest_sha256':sha(METRIC/'VENDOR.json'),'grid_size':55,'mask':None,'tracks_dtype':'torch.float32','torch_version':u['expected_runtime']['torch_version'],'cuda_version':u['expected_runtime']['cuda_version'],'tracks_shape':[3025,49,2]}
 reports={}
 for role in ['reference','native']:
  folder=ROOT/'cache'/role;r=read(folder/'REPORT.json');b=read(folder/'R98_BINDING.json')
  require(r.get('passed') is True and r['case']['id']==CASE and r['case']['role']==('reference' if role=='reference' else 'generated'),'cached role/case changed')
  for k,v in expected.items():require(r[k]==v,'cached tracker setup differs: '+k)
  for k in ['hostname','gpu_name']:require(r['admission_before_cuda'][k]==u['expected_runtime'][k],'cached host/model differs')
  times=[float(x['best_effort_timestamp_time']) for x in r['timebase']['frames']]
  require(len(times)==49 and all(math.isfinite(t) and abs(t-i/8)<1e-6 for i,t in enumerate(times)),'cached physical time changed')
  require(sha(folder/'tracks.pt')==r['tracks_sha256'] and b['report']['sha256']==sha(folder/'REPORT.json'),'cached tracks/report changed')
  reg=b['root_registration'];require(reg['consumer_freeze_sha256']==sha(ROOT/'cache/R98_CONSUMER_FREEZE.json') and b['administrative_wrapper']['sha256']==sha(ROOT/'cache/R98_track_shared.py'),'cached execution wrapper changed')
  require(reg['input_manifest']['sha256']==r['manifest_sha256'],'cached input registration differs')
  release=read(ROOT/'cache'/(role+'_RELEASED.json'));require(release['pid']==r['pid'] and release['returncode']==0 and release['process_absent'] and release['own_cuda_absent'] and release['peer_removed'],'cached tracking lifecycle incomplete')
  reports[role]=r
 src=read(METRIC/'SOURCE_INPUTS.json');require(reports['reference']['case']==src['inputs'][0] and reports['reference']['manifest_sha256']==sha(METRIC/'SOURCE_INPUTS.json'),'cached original source differs')
 require(sha(METRIC/src['inputs'][0]['file'])==u['source_original_sha256'],'source bytes changed')
 ni=read(ROOT/'cache/native_prepared/METRIC_INPUTS.json');mapping=read(ROOT/'cache/native_prepared/edited49_8fps.mapping.json');nt=read(ROOT/'cache/native_prepared/TRACK_INPUTS.json');nr=reports['native']
 require(nr['case']==nt['inputs'][0] and nr['manifest_sha256']==sha(ROOT/'cache/native_prepared/TRACK_INPUTS.json'),'cached Native manifest differs')
 require(ni['full158_output_sha256']==u['native_full_sha256'] and ni['full_output_indices']==INDICES and ni['physical_seconds']==[i/8 for i in range(49)] and ni['original_source_sha256']==u['source_original_sha256'],'cached Native source/timeline differs')
 require(mapping['source_sha256']==u['native_full_sha256'] and mapping['destination_sha256']==nr['case']['sha256']==ni['edited49_sha256'] and mapping['input_indices']==INDICES and mapping['decoded_frame_md5_equal'] is True,'cached Native release differs')
 require(nr['generation_binding_checked']=={'metric_inputs_sha256':sha(ROOT/'cache/native_prepared/METRIC_INPUTS.json'),'release_mapping_sha256':sha(ROOT/'cache/native_prepared/edited49_8fps.mapping.json'),'full158_sha256':u['native_full_sha256']},'cached Native generation binding differs')
 score=read(ROOT/'cache/NATIVE_SCORE.json');require(score['actual_generated_video_sha256']==u['native_full_sha256'] and score['score']==u['native_score'] and score['valid_frames']==147 and score['evaluation_frames']==49 and score['evaluation_fps']==8,'cached Native score differs')
 require(score['reference_report']['sha256']==sha(ROOT/'cache/reference/REPORT.json') and score['edited_report']['sha256']==sha(ROOT/'cache/native/REPORT.json') and score['metric_inputs']['sha256']==sha(ROOT/'cache/native_prepared/METRIC_INPUTS.json'),'cached score evidence differs')
 return reports

def validate_gate(g,media):
 c=read(ROOT/'configs/r101_consumer_contract.json');required=read(ROOT/'configs/GATE_REQUIRED_CHECKS.json')
 require(g.get('schema')=='r101-historical-native-paired-runtime-gate-v1' and g.get('passed') is True,'R101 actual paired gate missing/failed')
 checks=g.get('checks',{});require(checks and all(v is True for v in checks.values()) and all(checks.get(k) is True for k in required),'actual paired checks missing/failed')
 require(g['source_id']==c['source_id'] and g['prompt_version']=='actual-parent-P1-verbatim' and g['runtime_profile_sha256']==c['producer_runtime_sha256'],'actual source/prompt/runtime differs')
 require((g['valid_frames'],g['total_frames'],g['fps'],g['evaluation_crop_xywh'])==(147,158,24,[0,0,1152,768]),'actual physical domain differs')
 require(media['source']['sha256']==c['media']['source']['sha256'] and media['native']['sha256']==c['media']['native']['sha256'],'actual parent media differs')
 for role,routes in [('native',0),('forced',450)]:
  run=g['runs'][role];p=run['video']['properties'];require(run['video']['sha256']==media[role]['sha256'],'actual generated video differs')
  require(run['run_id']==c['parent_run_id' if role=='native' else 'run_id'],'actual run differs')
  require((run['valid_frames'],run['NFE'],run['Euler_updates'],run['routed_blocks'])==(147,20,20,routes),'actual counts differ')
  require((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1152,768,158,'24/1'),'actual output shape differs')
 require(g['runs']['native']['historical_parent'] is True and g['first_allowed_prediction_divergence_index']==6,'actual parent/prefix differs')
 rows=g['prefix_tensor_comparison'];require(len(rows)==6 and all(x['step_zero_based']==i and x['video'] is True and x['audio'] is True for i,x in enumerate(rows)),'actual prefix checks differ')
 return g
