"""IVEBench pinned official MF, with explicit five-task media/time binding.

No metric formula is changed. Call --check-only for CPU-only import/binding checks.
Model evaluation requires a manifest naming real source/edited files and an
explicit --device. CUDA resource admission remains the experiment owner's job.
"""
import argparse, hashlib, json, math, os, subprocess, sys, time
from pathlib import Path
LITERATURE = Path(__file__).resolve().parents[1]
COMMIT = '2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
WEIGHT_SHA = 'da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
SELECTION_SHA = '5d4f43a066dffa7227e062c5914734f1d406627d10c2c1c8cdf0388e25ad8fd9'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON constant')))

def verify_vendor():
    entries=read_json(LITERATURE/'OFFICIAL_SOURCE_SHA.json')
    for x in entries:
        p=LITERATURE/'official_source'/x['path']
        if p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:
            raise ValueError('official source changed: '+x['path'])
    return {'commit':COMMIT,'files':len(entries),'manifest_sha256':sha(LITERATURE/'OFFICIAL_SOURCE_SHA.json')}

def official_class():
    verify_vendor()
    sys.path.insert(0,str(LITERATURE/'official_source/metrics'))
    from fidelity.motion_fidelity import MotionFidelityEvaluator
    return MotionFidelityEvaluator

def bound_file(row):
    if not isinstance(row,dict) or set(('file','sha256'))-row.keys():
        raise ValueError('file binding requires file and sha256')
    p=Path(row['file'])
    if not p.is_file() or sha(p)!=row['sha256']:
        raise ValueError('file SHA mismatch: '+str(p))
    return p

def media_info(path,ffprobe):
    raw=subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],text=True)
    d=json.loads(raw);s=d['streams'][0];pts=[float(f['best_effort_timestamp_time']) for f in d['frames']]
    if not pts or not all(math.isfinite(t) for t in pts):raise ValueError('invalid PTS')
    return {'width':s['width'],'height':s['height'],'count':len(pts),'pts_s':pts,'avg_frame_rate':s['avg_frame_rate']}

def validate_time_view(info,count):
    if (info['width'],info['height'],info['count'])!=(1280,720,count):
        raise ValueError('score media must be fixed 1280x720 effective prefix')
    if len(info['pts_s'])!=count or any(not math.isfinite(t) or abs(t-i/24)>1e-6 for i,t in enumerate(info['pts_s'])):
        raise ValueError('score media must retain declared 24fps physical samples')

def validate_full_view(info):
    if (info['width'],info['height'],info['count'])!=(1312,736,90):
        raise ValueError('prepared/full media must be 1312x736 and90 frames')
    if len(info['pts_s'])!=90 or any(not math.isfinite(t) or abs(t-i/24)>1e-6 for i,t in enumerate(info['pts_s'])):
        raise ValueError('prepared/full media must retain24fps physical samples')

def validate_source_provenance(record,expected,prepared_sha,decoded_hashes):
    count=expected['input_protocol']['effective_frame_count']
    mapping=expected['input_protocol']['input_to_original_frame']
    fields={'schema':'r54-ivebench-input-v1','pair_id':expected['pair_id'],
            'selection_sha256':SELECTION_SHA,'source_sha256':expected['source']['sha256'],
            'video_sha256':prepared_sha,'geometry':[1312,736],
            'content_rectangle_xywh':[16,8,1280,720],'frames':90,'fps':24,
            'effective_frame_count':count,'evaluate_indices':list(range(count)),
            'input_to_original_frame':mapping,'padding_indices':list(range(count,90)),
            'decoded_pixel_mapping_exact':True,'prompt':expected['edit_prompt'],
            'reference_images':[]}
    for key,value in fields.items():
        if record.get(key)!=value:raise ValueError('source preparation record mismatch: '+key)
    original_hashes=record['original_transformed_frame_md5']
    if len(original_hashes)!=expected['source']['frame_count']:
        raise ValueError('source preparation original decoded frame count differs')
    if record['input_frame_md5']!=decoded_hashes or decoded_hashes!=[original_hashes[i] for i in mapping]:
        raise ValueError('prepared source pixels differ from recorded original-frame mapping')

def frame_hashes(path,ffmpeg,vf=None):
    cmd=[ffmpeg,'-v','error','-threads','2','-i',str(path),'-an']
    if vf:cmd+=['-vf',vf]
    cmd+=['-vsync','0','-pix_fmt','yuv420p','-threads','2','-f','framemd5','-']
    text=subprocess.check_output(cmd,text=True)
    return [line.split(',')[-1].strip() for line in text.splitlines() if line and not line.startswith('#')]

def validate_source_row(row,e,ffprobe,ffmpeg):
    count=e['input_protocol']['effective_frame_count']
    bound_file(row['source_original'])
    if row['source_original']['sha256']!=e['source']['sha256']:raise ValueError('wrong original source')
    if row.get('score_frame_indices')!=list(range(count)):raise ValueError('score prefix differs')
    if row.get('input_to_original_frame')!=e['input_protocol']['input_to_original_frame']:raise ValueError('source frame map differs')
    prepared=bound_file(row['source_prepared_video']);validate_full_view(media_info(prepared,ffprobe))
    prep_record=read_json(bound_file(row['source_preparation_record']))
    validate_source_provenance(prep_record,e,row['source_prepared_video']['sha256'],frame_hashes(prepared,ffmpeg))
    source=bound_file(row['source_score_video']);validate_time_view(media_info(source,ffprobe),count)
    crop=f'crop=1280:720:16:8,trim=end_frame={count},setsar=1'
    if frame_hashes(source,ffmpeg)!=frame_hashes(prepared,ffmpeg,crop):
        raise ValueError('source score pixels differ from actual H3 prepared-input crop/prefix')

def validate_edited_entry(entry,count,ffprobe,ffmpeg):
    target=bound_file(entry['score_video']);validate_time_view(media_info(target,ffprobe),count)
    for role in ['generation_record','release_record']:bound_file(entry[role])
    full=bound_file(entry['full_video']);validate_full_view(media_info(full,ffprobe))
    crop=f'crop=1280:720:16:8,trim=end_frame={count},setsar=1'
    if frame_hashes(target,ffmpeg)!=frame_hashes(full,ffmpeg,crop):
        raise ValueError('edited score crop/prefix decoded frames differ from full generation')

def validate_manifest(manifest_path,selection_path,ffprobe,ffmpeg):
    if sha(selection_path)!=SELECTION_SHA:raise ValueError('selection changed')
    selection=read_json(selection_path); d=read_json(manifest_path)
    if d.get('selection_sha256')!=SELECTION_SHA or d.get('schema')!='h3-ivebench-official-mf-inputs-v1':raise ValueError('input schema/selection mismatch')
    expected={x['pair_id']:x for x in selection['pairs']}
    methods=d.get('methods')
    if not isinstance(methods,list) or not methods or len(set(methods))!=len(methods):raise ValueError('unique method names required')
    items=d.get('pairs',[])
    if len(items)!=5 or {x.get('pair_id') for x in items}!=set(expected):raise ValueError('fixed five pairs required')
    for row in items:
        e=expected[row['pair_id']];count=e['input_protocol']['effective_frame_count']
        validate_source_row(row,e,ffprobe,ffmpeg)
        if set(row.get('edited',{}))!=set(methods):raise ValueError('missing/extra method')
        for method in methods:
            # Real upstream records are mandatory; scientific semantics are separately
            # reviewed by the producer/release owner and must be recorded accurately.
            validate_edited_entry(row['edited'][method],count,ffprobe,ffmpeg)
    return d,selection

def run(args):
    import torch
    torch.set_num_threads(2)
    vendor=verify_vendor();cls=official_class()
    checkpoint=Path(args.checkpoint)
    if not checkpoint.is_file() or sha(checkpoint)!=WEIGHT_SHA:raise ValueError('pinned CoTracker3 checkpoint required; hub fallback disabled')
    d,selection=validate_manifest(args.manifest,args.selection,args.ffprobe,args.ffmpeg)
    result={'schema':'h3-ivebench-official-mf-results-v1','official_commit':COMMIT,'vendor':vendor,'checkpoint_sha256':WEIGHT_SHA,'input_manifest_sha256':sha(args.manifest),'selection_sha256':SELECTION_SHA,'methods':d['methods'],'fixed_pairs':5,'scope':'five adapted 24fps short tasks; pinned MF implementation; not full IVEBench or12-metric leaderboard','check_only':args.check_only,'results':[]}
    if args.check_only:
        result['cuda_initialized']=torch.cuda.is_initialized()
    else:
        if args.device is None:raise ValueError('explicit --device required for tracking')
        if args.device=='cuda' and not os.environ.get('CUDA_VISIBLE_DEVICES'):raise ValueError('set admitted CUDA_VISIBLE_DEVICES explicitly')
        t=time.monotonic();evaluator=cls(str(checkpoint),device=args.device,grid_size=10,max_frames=None)
        result['model_load_s']=time.monotonic()-t
        for row in d['pairs']:
            for method in d['methods']:
                t=time.monotonic();entry={'pair_id':row['pair_id'],'method':method,'source_sha256':row['source_score_video']['sha256'],'edited_sha256':row['edited'][method]['score_video']['sha256']}
                try:
                    score=evaluator.compute_motion_similarity(row['source_score_video']['file'],row['edited'][method]['score_video']['file'])
                    if not math.isfinite(score):raise ValueError('nonfinite official score')
                    entry.update(status='ok',motion_fidelity=score)
                except Exception as error:
                    entry.update(status='error',motion_fidelity=None,error=repr(error))
                entry['elapsed_s']=time.monotonic()-t;result['results'].append(entry)
                Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        result['summary']={}
        for method in d['methods']:
            rs=[r for r in result['results'] if r['method']==method];valid=[r['motion_fidelity'] for r in rs if r['status']=='ok']
            result['summary'][method]={'fixed_denominator':5,'valid_count':len(valid),'failure_count':5-len(valid),'mean_if_all_five_valid':sum(valid)/5 if len(valid)==5 else None,'valid_only_mean':sum(valid)/len(valid) if valid else None}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--selection',required=True);p.add_argument('--checkpoint',default=str(LITERATURE/'weights/baseline_offline.pth'));p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--device',choices=['cpu','cuda']);p.add_argument('--check-only',action='store_true');p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(run(a),ensure_ascii=False,indent=2))
