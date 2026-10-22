"""CPU-only integrity and exact source-timebase verification. Imports no model code."""
import argparse,sys
from common import *
from render_native import media_info,check_time

def verify(ffprobe='/opt/homebrew/bin/ffprobe'):
    c=validate_static();producer=Path(c['producer_local'])
    require(sha(producer/'deploy_manifest.json')==c['producer_seal_sha256'],'producer seal changed')
    seal=read(producer/'deploy_manifest.json')
    for file,value in seal['files'].items():require(sha(producer/file)==value['sha256'],'producer file changed: '+file)
    science=read(ROOT/'configs/producer_scientific_contract.json')
    require(science['source_ids']==list(SOURCES),'producer source order differs')
    require(len(science['cases'])==6 and science['input_reference_images']==0,'producer task count or image input differs')
    rows=[]
    for source in SOURCES:
        p=info(source);provenance=read(ROOT/p['provenance']['file']);valid=p['valid_frames'];total=p['geometry']['frames']
        require(provenance['effective_frame_count']==valid and provenance['padding_indices']==list(range(valid,total)),'valid/padding split differs')
        require(provenance['evaluate_indices']==list(range(valid)) and provenance['content_rectangle_xywh']==p['crop_xywh'],'evaluation geometry differs')
        require(provenance['video_sha256']==p['source']['sha256'] and provenance['reference_images']==[],'source provenance differs')
        require(len(provenance['input_to_original_frame'])==total and provenance['decoded_pixel_mapping_exact'] is True,'source mapping missing')
        require(sha(p['original_media']['file'])==p['original_media']['sha256']==provenance['source_sha256'],'original source differs')
        for arm in ('native','forced'):
            run=p['run_id'] if arm=='native' else p['forced_run_id'];field='graph_sha256' if arm=='native' else 'forced_graph_sha256'
            verify_official_prompt(p,read(ROOT/'configs/graphs'/f'{run}.json'))
            actual=next(x for x in science['cases'] if x['run_id']==run)
            require(actual['source_id']==source and actual['arm']==arm and actual['valid_frame_count']==valid and actual['reference_image_count']==0,'actual registry differs')
            require(actual['prompt']==p['prompt'] and actual['task_scope']==p['task_scope'] and actual['evaluation_scope']==p['evaluation_scope'],'task/prompt scope differs')
            require(sha(ROOT/'configs/graphs'/f'{run}.json')==p[field]==sha(producer/'configs/graphs'/f'{run}.json'),'graph binding differs')
        properties=media_info(ROOT/p['source']['file'],ffprobe);check_time(properties,total,1312,736)
        rows.append({'source_id':source,'valid_frames':valid,'total_frames':total,'all_pts_verified':True,'reference_image':False,'evaluation_scope':p['evaluation_scope']})
    require('torch' not in sys.modules,'CPU consumer imported model runtime')
    return {'passed':True,'producer_files':len(seal['files']),'sources':rows,'CUDA_initialized':False,'GPU_started':False}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output');args=a.parse_args();result=verify()
    if args.output:save(args.output,result)
    print(json.dumps(result,ensure_ascii=False))
