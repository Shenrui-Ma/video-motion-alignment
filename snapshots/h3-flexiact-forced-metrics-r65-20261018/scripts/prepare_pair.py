"""Retain original158, create exact49@8 scoring videos with the frozen R49 sampler."""
import argparse,sys
from common import *
def prepare(source):
 verify_runtime();incoming=ROOT/'incoming'/source;collection=read(incoming/'COLLECTION.json');require(collection['source']==source,'collection source differs')
 for name,digest in collection['files'].items():require(Path(name).name==name and sha(incoming/name)==digest,'intake file changed')
 g=verify_gate(read(incoming/'PAIR_RUNTIME_GATE.json'),source);dest=ROOT/'prepared'/source;require(not dest.exists(),'prepared pair exists');dest.mkdir(parents=True)
 release=load('frozen_r49_release49',ROOT/'runtime/release/release49.py');tracker=load('frozen_flex_run_tracks',METRIC/'run_tracks.py');source_item=next(x for x in read(METRIC/'SOURCE_INPUTS.json')['inputs'] if x['id']==f'human/{source}/000')
 cases=read(ROOT/'configs/producer_scientific_contract.json')['cases'];source_provenance=read(ROOT/'inputs'/f'source_{source}_provenance.json');require(source_item['sha256']==source_provenance['source_original_sha256'],'original official source differs')
 for method in METHODS:
  row=g['runs'][method];run=row['run_id'];full=incoming/(method+'.mp4');require(sha(full)==row['video']['sha256'],'copied full158 differs')
  job=read(incoming/f'{method}_job.json');history=read(incoming/f'{method}_history.json');graph=read(incoming/f'{method}_graph.json');router=read(incoming/f'{method}_router.json')
  require(job['status']=='success' and job['name']==run and job['graph_sha256']==sha(incoming/f'{method}_graph.json') and history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'actual job binding differs')
  case=next(x for x in cases if x['run_id']==run);require(graph['5']['inputs']['prompt']==case['prompt'] and graph['21']['inputs']['image']==case['portrait'] and router['routed_calls']==row['routed_blocks'],'original identity/prompt/route differs')
  folder=dest/method;folder.mkdir();video=folder/'edited49_8fps.mp4';mapping=release.run(full,video)
  metric={'run_id':run,'method':method,'official_pair_id':source_item['id'],'edited49':str(video.resolve()),'edited49_sha256':sha(video),'full158_output':str(full.resolve()),'full158_output_sha256':sha(full),'full_output_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'padding_evaluated':False,'original_source_sha256':source_item['sha256'],'producer_receipt':bound(incoming/'PAIR_RUNTIME_GATE.json'),'source_provenance':bound(ROOT/'inputs'/f'source_{source}_provenance.json')};save(folder/'METRIC_INPUTS.json',metric)
  item={'id':source_item['id'],'method':method,'role':'generated','file':str(video.resolve()),'sha256':sha(video),'generation_frame_indices':INDICES,'generation_binding':{'metric_inputs':bound(folder/'METRIC_INPUTS.json'),'release_mapping':bound(video.with_suffix('.mapping.json'))}}
  tracker.validate_generated_binding(item,video);tracker.check_timebase(video)
  save(folder/'TRACK_INPUTS.json',{'schema':'r65-fresh-flex-generated-tracking-v1','inputs':[item],'runtime_freeze_sha256':sha(METRIC/'RUNTIME_FREEZE.json'),'paired_intake':bound(incoming/'COLLECTION.json')})
 save(dest/'READY.json',{'passed':True,'source':source,'producer_receipt':bound(incoming/'PAIR_RUNTIME_GATE.json'),'official_frame_indices':INDICES,'geometry':[1152,768],'fps':8,'source_tracking':'fresh_host41','methods':list(METHODS),'runtime_freeze_sha256':sha(METRIC/'RUNTIME_FREEZE.json')});return dest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);a=p.parse_args()
 with cpu_lock():print(prepare(a.source))
