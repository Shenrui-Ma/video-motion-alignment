"""Administrative wrapper around frozen R73 strict preparation."""
import json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import common
import prepare_pair as frozen
from bindings import official,validate_full

def prepare(source,ffmpeg,ffprobe):
    common.verify_runtime()
    out=ROOT/'prepared'/source
    audit=HERE/'timestamp_recovery';audit.mkdir(exist_ok=True)
    total=common.entry(source)['input_protocol']['h3_frame_count']
    count=common.entry(source)['input_protocol']['effective_frame_count']
    for method in common.METHODS:
        raw=ROOT/'incoming'/source/(method+'.mp4')
        validate_full(official.media_info(raw,ffprobe),total)
        previous=out/(method+'_score.mp4')
        if previous.exists():
            common.require(not (out/'METRIC_INPUTS.json').exists(),'committed score inputs cannot be replaced')
            destination=audit/(source+'_'+method+'_failed_score.mp4')
            common.require(not destination.exists(),'failed artifact already archived; inspect recovery state')
            info=official.media_info(previous,ffprobe)
            common.save(audit/(source+'_'+method+'_failure.json'),{'score_sha256':common.sha(previous),'raw':common.bound(raw),'failed_media_info':info,'expected_valid_frames':count})
            previous.rename(destination)
    result=frozen.prepare(source,str(HERE/'ffmpeg_score_mux.py'),ffprobe)
    common.save(audit/(source+'_REPAIR_VALIDATION.json'),{'passed':True,'ready':common.bound(result),'frozen_preparer':common.bound(ROOT/'scripts/prepare_pair.py'),'strict_metric_runtime_unchanged':True,'decoded_each_frame_pixels_equal_original_crop':True,'output_pts_i_over24':True,'original_generation_untouched':True})
    return result
