"""Exact official score, directional edited-to-reference; cached Native retained."""
import os,sys,time
from common import *
def main():
 os.environ['CUDA_VISIBLE_DEVICES']='';verify_runtime();cached=validate_cache();require((ROOT/'prepared/guided/MATCHED_GATE_BINDING.json').is_file(),'actual guided input pending')
 import torch
 torch.set_num_threads(2);sys.path.insert(0,str(METRIC));scorer=load('official_scorer',METRIC/'score_pair.py')
 reference,s=scorer.read_tracks(ROOT/'cache/reference',torch);target,t=scorer.read_tracks(ROOT/'tracks/guided',torch);b=read(ROOT/'tracks/guided/R101_BINDING.json')
 require(b['report']['sha256']==sha(ROOT/'tracks/guided/REPORT.json') and b['root_registration']['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json') and b['administrative_wrapper']['sha256']==sha(ROOT/'scripts/track_shared.py'),'guided tracker registration differs')
 require(b['root_registration']['input_manifest']['sha256']==sha(ROOT/'prepared/guided/TRACK_INPUTS.json')==t['manifest_sha256'] and t['case']==read(ROOT/'prepared/guided/TRACK_INPUTS.json')['inputs'][0],'guided tracker input differs')
 for k in ['torch_version','cuda_version','checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype']:require(s[k]==t[k],'cached/new tracker environment differs: '+k)
 for k in ['hostname','gpu_name']:require(s['admission_before_cuda'][k]==t['admission_before_cuda'][k],'cached/new host/model differs')
 adapter=load('official_adapter',METRIC/'metric_adapter.py');start=time.monotonic();record,matrix=adapter.score_tracks(target,reference);dest=ROOT/'scores/guided';dest.mkdir(parents=True,exist_ok=False);torch.save({'similarity_matrix':matrix},dest/'similarity.pt')
 old=read(ROOT/'cache/NATIVE_SCORE.json');mi=read(ROOT/'prepared/guided/METRIC_INPUTS.json')
 record.update({'method':'fixed6..14','actual_generated_video_sha256':mi['full158_output_sha256'],'native_score':old['score'],'delta':record['score']-old['score'] if record['score'] is not None else None,'cached_native_score':bound(ROOT/'cache/NATIVE_SCORE.json'),'cache_reuse_receipt':bound(ROOT/'configs/CACHE_REUSE.json'),'reference_report':bound(ROOT/'cache/reference/REPORT.json'),'edited_report':bound(ROOT/'tracks/guided/REPORT.json'),'metric_inputs':bound(ROOT/'prepared/guided/METRIC_INPUTS.json'),'actual_gate':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),'official_commit':'de9fe1d536732c4d1a384577b5ae54f8fc1730d7','valid_frames':147,'evaluation_frames':49,'evaluation_fps':8,'score_seconds':time.monotonic()-start,'cuda_initialized':torch.cuda.is_initialized(),'scope':'official-assets crosspair; task fidelity and event timing are evaluated separately'})
 save(dest/'SCORE.json',record);print(json.dumps(record,allow_nan=False))
if __name__=='__main__':main()
