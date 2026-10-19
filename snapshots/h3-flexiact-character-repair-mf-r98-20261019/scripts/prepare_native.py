"""CPU only: bind actual R98 Native and derive exact official49 frames."""
from common import *
def validate_gate(g,video_sha):
 require(g.get('schema')=='r98-character-repair-native-runtime-gate-v1' and g.get('passed') is True and all(g['checks'].values()),'actual R98 Native gate not PASS')
 require(g['run_id']=='r98_human2animal_1__game_man_4_seed2026101701_native' and g['video']['sha256']==video_sha,'wrong actual Native')
 require(g['routed_blocks']==0 and g['NFE']==g['Euler_updates']==20 and g['valid_frames']==147,'Native execution/frame protocol differs')
 require(g['video']['properties']['width']==1152 and g['video']['properties']['height']==768 and g['video']['properties']['nb_read_frames']=='158','actual output shape differs')
def prepare():
 verify_runtime();full=ROOT/'incoming/native.mp4';gate=ROOT/'incoming/NATIVE_RUNTIME_GATE.json';g=read(gate);validate_gate(g,sha(full));folder=ROOT/'prepared/native';folder.mkdir(exist_ok=False)
 release=load('r98_unchanged_release49',ROOT/'runtime/release/release49.py');video=folder/'edited49_8fps.mp4';release.run(full,video)
 ref=read(METRIC/'SOURCE_INPUTS.json')['inputs'][0]
 record={'run_id':g['run_id'],'method':'native','official_pair_id':CASE,'official_pair_id_scope':'canonical motion-source key; actual pair human2animal_1/game_man_4 is official-assets crosspair','edited49':str(video.resolve()),'edited49_sha256':sha(video),'full158_output':str(full.resolve()),'full158_output_sha256':sha(full),'full_output_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,'original_source_sha256':ref['sha256'],'producer_receipt':bound(gate)}
 save(folder/'METRIC_INPUTS.json',record)
 item={'id':CASE,'method':'native','role':'generated','file':str(video.resolve()),'sha256':sha(video),'generation_frame_indices':INDICES,'generation_binding':{'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'release_mapping':bound(video.with_suffix('.mapping.json'))}}
 tracker=load('r98_frozen_tracker',METRIC/'run_tracks.py');tracker.validate_generated_binding(item,video);tracker.check_timebase(video);tracker.check_timebase(METRIC/ref['file'])
 save(folder/'TRACK_INPUTS.json',{'schema':'r98-generated-tracking-v1','inputs':[item],'actual_native_gate':bound(gate),'case':CASE})
 save(folder/'READY.json',{'passed':True,'method':'native','gate':bound(gate),'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'tracker_manifest':bound(folder/'TRACK_INPUTS.json'),'indices':INDICES,'fps':8,'new_guided':'PENDING_R101_MATCHED_GATE'})
 print(json.dumps({'READY':str(folder/'READY.json'),'CUDA_started':False}))
if __name__=='__main__':prepare()
