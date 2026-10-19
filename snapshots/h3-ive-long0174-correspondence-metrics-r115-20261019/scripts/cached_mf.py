"""Reuse exact official source/Native tracks after pixel, setting and result checks."""
from common import ROOT,read,sha,require,bound
import numpy as np

BASE=ROOT.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r107_long_0174'
CASE=BASE/'cases/r107_long_0174'
ACTUAL=BASE/'actual_host41/cases/r107_long_0174'
COMMIT='2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
CHECKPOINT='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
VENDOR='6335a8195c9976fb8264d3f1dcf9e0be7bef53620ccef4f93b3dcd42d295be81'
TRACKER={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}

def validate_report(report,role,manifest):
    require(role in ('source','native') and report['passed'] is True and report['method']==role,'cached role/status differs')
    require(report['checkpoint_sha256']==CHECKPOINT and report['official_commit']==COMMIT and report['vendor']['manifest_sha256']==VENDOR,'official tracker/checkpoint differs')
    require(report['tracker']==TRACKER and report['effective_frame_count']==145 and report['score_frame_indices']==list(range(145)),'official physical domain/settings differ')
    require(manifest['valid_frames']==145 and manifest['total_frames']==158 and manifest['fps']==24 and manifest['crop_xywh']==[16,8,1280,720],'input physical domain differs')
    require(report['score_video']['sha256']==manifest['roles'][role]['score_sha256'] and report['decoded_frame_md5']==manifest['roles'][role]['score_frame_md5'],'cached score pixels differ')

def verify_reuse(full_by_role):
    from media import info,check_time,frame_hashes
    manifest=read(CASE/'INPUTS.json');inputs_sha=sha(CASE/'INPUTS.json')
    require(inputs_sha=='af5f75f62fdfee9d7ceb1f027b167c2860263056f3cc621403f061d31e2c6ed9','registered cache manifest changed')
    result=read(ACTUAL/'results/native.json');verified=read(BASE/'RESULT_VERIFIED.json')
    require(sha(ACTUAL/'results/native.json')==verified['scores']['native']['sha256'],'verified native score changed')
    require(result['checkpoint_sha256']==CHECKPOINT and result['official_vendor']['commit']==COMMIT and result['official_vendor']['manifest_sha256']==VENDOR,'cached score method differs')
    rows={}
    for role in ('source','native'):
        record=manifest['roles'][role];full=full_by_role[role];score=CASE/record['score_file'];track=ACTUAL/'tracks'/role/'tracks.npz';report_file=track.with_name('REPORT.json');report=read(report_file)
        validate_report(report,role,manifest)
        require(sha(full)==record['full_sha256'] and sha(score)==record['score_sha256'],'registered full video differs from cached tracker input')
        require(report['input_manifest']['sha256']==inputs_sha and sha(track)==report['tracks_sha256'],'cache input/tracks binding differs')
        require(report['source_prepared_sha256']==manifest['roles']['source']['full_sha256'] and report['source_score_sha256']==manifest['roles']['source']['score_sha256'],'reference source binding differs')
        check_time(info(full),158,1312,736);check_time(info(score),145,1280,720)
        require(frame_hashes(full,'crop=1280:720:16:8,trim=end_frame=145,setsar=1')==frame_hashes(score)==report['decoded_frame_md5'],'decoded crop pixels differ from actual cache')
        with np.load(track,allow_pickle=False) as z:
            require(set(z.files)=={'tracks','visibility'} and z['tracks'].shape==(1,145,100,2) and z['visibility'].shape==(1,145,100),'cached tracker shape differs')
        key='source' if role=='source' else 'target'
        require(result[key+'_report']['sha256']==sha(report_file) and result[key+'_tracks_sha256']==sha(track),'native result track provenance differs')
        release=verified['tracks'][role]['released']
        require(release['process_absent'] is True and release['own_cuda_absent'] is True and release['returncode']==0,'original tracker release missing')
        rows[role]={'full_video':bound(full),'score_video':bound(score),'frame_md5':report['decoded_frame_md5'],
            'cached_tracks':bound(track),'cached_tracker_report':bound(report_file),'tracker_reused':True,
            'original_runtime':{'torch':report['torch_version'],'cuda':report['cuda_version'],'gpu_uuid':report['gpu_uuid']}}
    require(result['actual_generated_video_sha256']==manifest['roles']['native']['full_sha256'] and result['case_inputs_sha256']==inputs_sha,'native score output binding differs')
    require(result['motion_fidelity']==verified['native'],'native score disagreement')
    return {'status':'EXACT_SOURCE_AND_NATIVE_CACHE_VERIFIED','roles':rows,'native_score':result['motion_fidelity'],
        'native_score_receipt':bound(ACTUAL/'results/native.json'),'verified_result':bound(BASE/'RESULT_VERIFIED.json'),
        'input_manifest':bound(CASE/'INPUTS.json'),'official_commit':COMMIT,'checkpoint_sha256':CHECKPOINT,
        'official_vendor_manifest_sha256':VENDOR,'tracker':TRACKER,'GPU_started':False,
        'reuse_scope':'Identical source/native pixels, valid physical frames, crop, checkpoint and official settings; recorded original runtime retained.'}
