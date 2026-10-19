"""One-time read-only five-source intake; no pose extraction or motion scoring."""
import fcntl,hashlib,json,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
with LOCK.open('a') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('CPU_LOCK_BUSY');sys.exit(75)
    start=time.monotonic()
    sys.path.insert(0,str(ROOT/'scripts'))
    from pose_domain import validate_pose
    path=Path('/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017/analysis/source_pose158_sidecar/MANIFEST.json')
    assert sha(path)=='090f382a6c00a94dd41d2ffc1c053923d632f32bb5056d7161f5083d3ba4c61a'
    manifest=read(path);binding=read(ROOT/'design/SOURCE_BINDING.json')
    assert manifest['status']=='complete' and manifest['producer_manifest_sha256']==binding['native_manifest_sha256']
    assert list(manifest['sources'])==binding['case_order']
    results={}
    for case in binding['cases']:
        sid=case['source_id'];s=manifest['sources'][sid]
        assert s['status']=='complete' and s['source_id']==sid and s['video_sha256']==case['video_sha256']==sha(s['video_path'])
        assert s['valid_observation_frames']==[0,146] and s['padding_frames']==[147,157] and s['original_sample_indices']==list(range(0,145,3))
        assert s['pose_sha256']==sha(s['pose_path']) and s['provenance_sha256']==sha(s['provenance_path'])
        raw=validate_pose(s['pose_path'],SimpleNamespace(**s['geometry']))
        assert raw['video']['sha256']==s['video_sha256'] and raw['extraction']=={'start':0,'end':None,'stride':1}
        prov=read(s['provenance_path'])
        assert prov['pose_provenance']==raw['provenance'] and prov['pose_sha256']==s['pose_sha256'] and prov['input_provenance_sha256']==case['provenance_sha256']
        results[sid]={'status':'FINITE_COMPLETE_158_POSE_ACCEPTED','pose_path':s['pose_path'],'pose_sha256':s['pose_sha256'],'remote_pose_path':s['remote_pose_path'],'video_sha256':s['video_sha256'],'provenance_sha256':s['provenance_sha256'],'raw_frame_count':len(raw['frames']),'full_intake_persons':sum(len(x['persons']) for x in raw['frames']),'geometry':s['geometry'],'observation_domain':[0,146],'padding_domain':[147,157]}
    result={'schema':'r50-real-source-pose-intake-v1','status':'SOURCE_INTAKE_PASS_PARENT_OUTPUTS_PENDING','sources':results,'source_manifest':str(path),'source_manifest_sha256':sha(path),'pose_guard_sha256':sha(ROOT/'scripts/pose_domain.py'),'validator_sha256':sha(__file__),'seconds':time.monotonic()-start,'new_model_or_pose_calls':0,'motion_scores_computed':False,'production_ready':False}
    with (ROOT/'audit/SOURCE_POSE_ACTUAL_INTAKE_v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'sources':len(results),'seconds':result['seconds']}))
