"""Release the same 49 original physical times, with actual paired provenance."""
from common import *
def prepare():
 verify_runtime();validate_cache();i=read(ROOT/'incoming/INTAKE.json')
 for n,h in i['files'].items():require(sha(ROOT/'incoming'/n)==h,'actual intake changed: '+n)
 mf=read(ROOT/'incoming/R101_MF_INPUTS.json');g=validate_gate(read(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),mf['media']);full=ROOT/'incoming/forced.mp4';require(sha(full)==g['runs']['forced']['video']['sha256'],'actual guided bytes differ')
 folder=ROOT/'prepared/guided';folder.mkdir(parents=True,exist_ok=False);video=folder/'edited49_8fps.mp4'
 release=load('unchanged_release49',ROOT/'runtime/release/release49.py');release.run(full,video)
 ref=read(METRIC/'SOURCE_INPUTS.json')['inputs'][0]
 record={'run_id':g['runs']['forced']['run_id'],'method':'guided','official_pair_id':CASE,'official_pair_id_scope':'canonical source key; this is the official-assets human2animal_1/game_man_4 crosspair','edited49':str(video.resolve()),'edited49_sha256':sha(video),'full158_output':str(full.resolve()),'full158_output_sha256':sha(full),'full_output_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,'original_source_sha256':ref['sha256'],'producer_receipt':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json')}
 save(folder/'METRIC_INPUTS.json',record)
 item={'id':CASE,'method':'guided','role':'generated','file':str(video.resolve()),'sha256':sha(video),'generation_frame_indices':INDICES,'generation_binding':{'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'release_mapping':bound(video.with_suffix('.mapping.json'))}}
 tracker=load('frozen_tracker',METRIC/'run_tracks.py');tracker.validate_generated_binding(item,video);tracker.check_timebase(video)
 save(folder/'TRACK_INPUTS.json',{'schema':'r101-generated-tracking-v1','inputs':[item],'actual_paired_gate':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),'case':CASE})
 save(folder/'MATCHED_GATE_BINDING.json',{'passed':True,'gate':bound(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),'full_generated_sha256':sha(full),'native_cache':bound(ROOT/'configs/CACHE_REUSE.json'),'method':'fixed steps6..14; no onlineobserver','valid_frames':147,'original_source_fps':8})
 save(folder/'READY.json',{'passed':True,'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'tracker_manifest':bound(folder/'TRACK_INPUTS.json'),'indices':INDICES,'fps':8,'new_tracking_needed':'guided only','GPU_started':False})
 print(json.dumps({'READY':str(folder/'READY.json'),'CUDA_started':False}))
if __name__=='__main__':prepare()
