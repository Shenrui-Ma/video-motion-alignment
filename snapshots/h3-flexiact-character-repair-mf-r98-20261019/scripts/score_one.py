"""Unchanged official MF numerics, with new-output/host/registration binding."""
import argparse,os,time,sys
from common import *
sys.path.insert(0,str(METRIC))
def checked(folder,method,torch):
 report=read(folder/'REPORT.json');binding=read(folder/'R98_BINDING.json')
 require(binding['report']['sha256']==sha(folder/'REPORT.json'),'report changed')
 require(binding['root_registration']['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json') and binding['administrative_wrapper']['sha256']==sha(ROOT/'scripts/track_shared.py'),'wrapper/freeze differs')
 require(binding['root_registration']['input_manifest']['sha256']==report['manifest_sha256'],'registered input differs')
 require(report['case']['id']==CASE and report['case']['role']==('reference' if method=='reference' else 'generated'),'source/edited direction mismatch')
 if method!='reference':
  manifest=ROOT/'prepared'/method/'TRACK_INPUTS.json';require(report['case']==read(manifest)['inputs'][0] and sha(manifest)==report['manifest_sha256'],'wrong target output')
 scorer=load('r98_frozen_score_pair',METRIC/'score_pair.py');return scorer.read_tracks(folder,torch)
def score(method):
 os.environ['CUDA_VISIBLE_DEVICES']='';verify_runtime();require(method in ['native','guided'],'unknown edited method')
 if method=='guided':require((ROOT/'prepared/guided/MATCHED_GATE_BINDING.json').is_file(),'actual guided binding pending')
 import torch
 torch.set_num_threads(2)
 reference,s=checked(ROOT/'tracks/reference','reference',torch);target,t=checked(ROOT/'tracks'/method,method,torch)
 for k in ['torch_version','cuda_version','checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype']:require(s[k]==t[k],'same tracker environment required: '+k)
 for k in ['hostname','gpu_name']:require(s['admission_before_cuda'][k]==t['admission_before_cuda'][k],'same source/target host/GPU model required: '+k)
 adapter=load('r98_frozen_adapter',METRIC/'metric_adapter.py');start=time.monotonic();record,matrix=adapter.score_tracks(target,reference)
 dest=ROOT/'scores'/method;dest.mkdir(parents=True,exist_ok=False);torch.save({'similarity_matrix':matrix},dest/'similarity.pt')
 record.update({'run_id':read(ROOT/'prepared'/method/'METRIC_INPUTS.json')['run_id'],'method':method,'actual_generated_video_sha256':read(ROOT/'prepared'/method/'METRIC_INPUTS.json')['full158_output_sha256'],'reference_report':bound(ROOT/'tracks/reference/REPORT.json'),'edited_report':bound(ROOT/'tracks'/method/'REPORT.json'),'metric_inputs':bound(ROOT/'prepared'/method/'METRIC_INPUTS.json'),'official_commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','valid_frames':147,'evaluation_frames':49,'evaluation_fps':8,'similarity_sha256':sha(dest/'similarity.pt'),'score_seconds':time.monotonic()-start,'cuda_initialized':torch.cuda.is_initialized(),'scope':'official-assets human2animal_1/game_man_4 crosspair; score does not certify identity, scene, action type or physical phase'})
 save(dest/'SCORE.json',record);print(json.dumps(record,allow_nan=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--method',choices=['native','guided'],required=True);a=p.parse_args();score(a.method)
