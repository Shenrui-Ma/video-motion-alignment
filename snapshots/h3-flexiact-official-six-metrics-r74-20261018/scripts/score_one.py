"""Use the unchanged official MF function with explicit source-cache provenance."""
import argparse,math,os,time
from common import *

def checked_tracking(folder,role,pair,config,torch):
 folder=Path(folder);p=pair_info(pair);action=p['motion_source_id'];report=read(folder/'REPORT.json')
 require(report['passed'] is True and report['tracks_sha256']==sha(folder/'tracks.pt'),'tracking output incomplete/changed')
 require(report['case']['role']==role and report['case']['id']==p['reference_id'],'tracking direction/source identity differs')
 times=[float(x['best_effort_timestamp_time']) for x in report['timebase']['frames']]
 require(len(times)==49 and all(math.isfinite(t) and abs(t-i/8)<1e-6 for i,t in enumerate(times)),'physical timebase differs')
 expected={'checkpoint_sha256':'dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3','metric_functions_sha256':sha(METRIC/'METRIC_FUNCTIONS.json'),'vendor_manifest_sha256':sha(METRIC/'VENDOR.json'),'grid_size':55,'mask':None,'tracks_dtype':'torch.float32'}
 require(all(report.get(k)==v for k,v in expected.items()),'tracker numeric protocol differs')
 if True:
  b=read(folder/'R74_BINDING.json');require(b['report']['sha256']==sha(folder/'REPORT.json') and b['frozen_numerical_tracker']['sha256']==sha(METRIC/'run_tracks.py') and b['administrative_wrapper']['sha256']==sha(ROOT/'scripts/track_shared.py') and b['root_registration']['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json'),'actual tracking wrapper/report binding differs')
  require(b['root_registration']['input_manifest']['sha256']==report['manifest_sha256'],'tracking input registration differs')
  if role=='reference':
   require(report['case']==source_item(action) and report['manifest_sha256']==sha(METRIC/'SOURCE_INPUTS.json'),'fresh source input differs')
  else:
   manifest=ROOT/'prepared'/pair/report['case']['method']/'TRACK_INPUTS.json';m=read(manifest)
   require(m['pair_key']==pair and report['case']==m['inputs'][0] and report['manifest_sha256']==sha(manifest),'generated pair input binding differs')
   tracker=load('r74_frozen_tracking_binding',METRIC/'run_tracks.py');video=Path(report['case']['file'])
   require(sha(video)==report['case']['sha256'] and tracker.validate_generated_binding(report['case'],video)==report['generation_binding_checked'],'generated frame release changed')
   mi=read(report['case']['generation_binding']['metric_inputs']['file']);require(all(mi[k]==p[k] for k in ['pair_key','motion_source_id','original_pair_id','group']),'generated task group differs')
 if role=='reference':require(sha(METRIC/source_item(action)['file'])==report['case']['sha256']==p['source_sha256'],'reference video changed')
 tracks=torch.load(folder/'tracks.pt',map_location='cpu',weights_only=True)['tracks'];require(list(tracks.shape)==[3025,49,2] and tracks.dtype==torch.float32,'actual track tensor shape/dtype differs')
 return tracks,report

def same_runtime(source,target):
 for key in ['torch_version','cuda_version','checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype']:require(source[key]==target[key],'source/target runtime differs: '+key)
 for key in ['hostname','gpu_name']:require(source['admission_before_cuda'][key]==target['admission_before_cuda'][key],'source/target hardware differs: '+key)

def run(pair,method):
 os.environ['CUDA_VISIBLE_DEVICES']='';require(method in METHODS,'unknown method');c=verify_runtime();p=pair_info(pair)
 import torch
 torch.set_num_threads(2)
 gate=ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json';verify_gate(read(gate),pair)
 source_dir=ROOT/'tracks/reference'/p['motion_source_id'];target_dir=ROOT/'tracks'/method/pair
 source,s=checked_tracking(source_dir,'reference',pair,c,torch);edited,t=checked_tracking(target_dir,'generated',pair,c,torch);require(t['case'].get('method')==method,'generated method differs');same_runtime(s,t)
 adapter=load('r74_official_metric_adapter',METRIC/'metric_adapter.py');dest=ROOT/'scores'/method/pair;dest.mkdir(parents=True,exist_ok=False);start=time.monotonic();record,matrix=adapter.score_tracks(edited,source)
 torch.save({'similarity_matrix':matrix},dest/'similarity.pt');record.update({**p,'method':method,'reference_report':bound(source_dir/'REPORT.json'),'edit_report':bound(target_dir/'REPORT.json'),'reference_tracks':bound(source_dir/'tracks.pt'),'edited_tracks':bound(target_dir/'tracks.pt'),'reference_reuse_receipt':bound(source_dir/'R74_SOURCE_REUSE.json') if (source_dir/'R74_SOURCE_REUSE.json').exists() else None,'timebase':'49 frames at original j/8 seconds','score_seconds':time.monotonic()-start,'cuda_initialized':torch.cuda.is_initialized(),'similarity_sha256':sha(dest/'similarity.pt'),'metric_adapter_sha256':sha(METRIC/'metric_adapter.py'),'producer_runtime_receipt':bound(gate),'metric_inputs':bound(ROOT/'prepared'/pair/method/'METRIC_INPUTS.json'),'edit_success':'PENDING_HUMAN_REVIEW'})
 save(dest/'SCORE.json',record);return record
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIR_KEYS,required=True);p.add_argument('--method',choices=METHODS,required=True);a=p.parse_args()
 with cpu_lock():print(json.dumps(run(a.pair,a.method)))
