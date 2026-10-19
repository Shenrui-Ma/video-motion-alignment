"""Preserve full158 outputs; derive official49 without moving physical timestamps."""
import argparse
from common import *
def prepare(pair):
 verify_runtime();p=pair_info(pair);action=p['motion_source_id'];incoming=ROOT/'incoming'/pair;collection=read(incoming/'COLLECTION.json');require(collection['source']==pair,'collection pair differs')
 for name,digest in collection['files'].items():require(Path(name).name==name and sha(incoming/name)==digest,'intake file changed')
 g=verify_gate(read(incoming/'PAIR_RUNTIME_GATE.json'),pair);dest=ROOT/'prepared'/pair;require(not dest.exists(),'prepared pair exists');dest.mkdir(parents=True)
 release=load('frozen_r49_release49',ROOT/'runtime/release/release49.py');tracker=load('frozen_flex_run_tracks',METRIC/'run_tracks.py');ref=source_item(action)
 cases=read(ROOT/'configs/producer_scientific_contract.json')['cases'];provenance=ROOT/'runtime/source_videos'/f'source_{action}_provenance.json'
 require(ref['sha256']==p['source_sha256'],'original source differs')
 for method in METHODS:
  row=g['runs'][method];run=row['run_id'];full=incoming/(method+'.mp4');require(sha(full)==row['video']['sha256'],'copied full158 differs')
  job=read(incoming/f'{method}_job.json');history=read(incoming/f'{method}_history.json');graph=read(incoming/f'{method}_graph.json');router=read(incoming/f'{method}_router.json')
  require(job['status']=='success' and job['name']==run and job['graph_sha256']==sha(incoming/f'{method}_graph.json') and history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'actual job binding differs')
  case=next(x for x in cases if x['run_id']==run);require(graph['5']['inputs']['prompt']==case['prompt'] and graph['21']['inputs']['image']==case['portrait'] and graph['22']['inputs']['file']==case['video'] and router['routed_calls']==row['routed_blocks'],'identity/prompt/source/route differs')
  folder=dest/method;folder.mkdir();video=folder/'edited49_8fps.mp4';release.run(full,video)
  metric={'run_id':run,'pair_key':pair,'original_pair_id':p['original_pair_id'],'group':p['group'],'motion_source_id':action,'method':method,'official_pair_id':ref['id'],'official_pair_id_field_scope':'legacy tracker key identifies shared motion source; original_pair_id identifies actual task','edited49':str(video.resolve()),'edited49_sha256':sha(video),'full158_output':str(full.resolve()),'full158_output_sha256':sha(full),'full_output_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,'original_source_sha256':ref['sha256'],'producer_receipt':bound(incoming/'PAIR_RUNTIME_GATE.json'),'source_provenance':bound(provenance)};save(folder/'METRIC_INPUTS.json',metric)
  item={'id':ref['id'],'method':method,'role':'generated','file':str(video.resolve()),'sha256':sha(video),'generation_frame_indices':INDICES,'generation_binding':{'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'release_mapping':bound(video.with_suffix('.mapping.json'))}}
  tracker.validate_generated_binding(item,video);tracker.check_timebase(video)
  save(folder/'TRACK_INPUTS.json',{'schema':'r66-generated-tracking-v1','inputs':[item],'pair_key':pair,'original_pair_id':p['original_pair_id'],'group':p['group'],'runtime_freeze_sha256':sha(METRIC/'RUNTIME_FREEZE.json'),'paired_intake':bound(incoming/'COLLECTION.json')})
 save(dest/'READY.json',{'passed':True,**p,'producer_receipt':bound(incoming/'PAIR_RUNTIME_GATE.json'),'official_frame_indices':INDICES,'geometry':[1152,768],'fps':8,'methods':list(METHODS),'runtime_freeze_sha256':sha(METRIC/'RUNTIME_FREEZE.json')});return dest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIR_KEYS,required=True);a=p.parse_args()
 with cpu_lock():print(prepare(a.pair))
