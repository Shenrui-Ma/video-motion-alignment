"""Read-only evidence checks and explicit, separately authorized CPU entry gates."""
from pathlib import Path
import hashlib,json,math,os

ROOT=Path(__file__).resolve().parents[1]
REMOTE_ROOT='/data5/researcher/h3_runs/timing_tta_phase_diagnostic_r36_20261017'

def read(p): return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def save(p,j):
    p=Path(p);require(not p.exists(),'Refuse overwrite: '+str(p));p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');require(not tmp.exists(),'Partial prior write exists')
    tmp.write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def item(name):
    rows=[x for x in read(ROOT/'INPUTS.json')['items'] if x['id']==name]
    require(len(rows)==1,'Unknown input item');return rows[0]
def validate_freeze():
    for manifest in ['DESIGN_FREEZE.json','FREEZE.json']:
        for name,digest in read(ROOT/manifest)['files'].items():
            p=ROOT/name;require(p.is_file() and not p.is_symlink() and sha(p)==digest,'Frozen file changed: '+name)
def authorize(phase):
    validate_freeze();a=read(ROOT/'AUTHORIZATION.json')
    require(a.get('approved') is True,'Root CPU allocation not approved')
    require(a.get('freeze_sha256')==sha(ROOT/'FREEZE.json') and a.get('protocol_sha256')==sha(ROOT/'PROTOCOL.json'),'Authorization binding')
    require(phase in a.get('phases',[]),'Phase not explicitly allocated')
    require(a.get('gpu_allowed') is False,'GPU prohibited')
    return a
def require_pruning_allows_pose():
    dest=ROOT/'results/identity_support_upper_bound';c=read(dest/'COMPLETE.json')
    require(c.get('status')=='complete' and c.get('freeze_sha256')==sha(ROOT/'FREEZE.json'),'Support pruning completion binding')
    require(set(c.get('files',{}))=={'RESULTS.json','SUMMARY.json'},'Support pruning exact inventory')
    require({q.name for q in dest.iterdir() if q.is_file()}=={'RESULTS.json','SUMMARY.json','COMPLETE.json'},'Support pruning output inventory')
    for name,digest in c['files'].items():require(sha(dest/name)==digest,'Support pruning output changed')
    s=read(dest/'SUMMARY.json');r=read(dest/'RESULTS.json')
    require(r['summary']==s and s.get('freeze_sha256')==sha(ROOT/'FREEZE.json') and s.get('protocol_sha256')==sha(ROOT/'PROTOCOL.json') and s.get('inputs_sha256')==sha(ROOT/'INPUTS.json'),'Support pruning input binding')
    require(len(r['rows'])==792 and s.get('rows')==792,'Support pruning all frozen rows')
    require(s.get('any_potentially_eligible') is True and any(x['dual_possibly_eligible'] is True for x in r['rows']),'No potentially eligible row: strict diagnostic stopped')
    return s
def video_pose_gate(entry,remote=False):
    video=Path(entry['remote_video' if remote else 'local_video']);pose=Path(entry['remote_identity_pose' if remote else 'local_identity_pose'])
    require(video.is_file() and sha(video)==entry['video_sha256'],'Video SHA')
    require(pose.is_file() and sha(pose)==entry['identity_pose_sha256'],'Identity pose full SHA')
    if entry['role']=='current_native_endpoint':
        request_path=video.parent/'request.json';decode_path=video.parent/'native.json'
        require(sha(request_path)==entry['request_sha256'] and sha(decode_path)==entry['decode_record_sha256'],'Current endpoint request/decode record SHA')
        request=read(request_path);decode=read(decode_path)
        require(request['branch']=='native' and request['run_id']==entry['run_id'] and request['seed']==entry['seed'] and request['physical_index']==entry['sampling_index_zero_based'] and request['request_id']==entry['request_id'],'Current trajectory/branch/index binding')
        require(request['endpoint_file_sha256']==entry['endpoint_sha256'] and decode['snapshot_sha256']==entry['endpoint_sha256'] and decode['request_sha256']==entry['request_sha256'],'Archived endpoint/decode lineage')
        require(decode['status']=='complete' and decode['output_sha256']==entry['video_sha256'] and decode['fallback_guard']['calls']==0 and decode['decoded_shape']==[141,736,1312,3] and decode['fps']==24,'Completed regular VAE decode')
    raw=read(pose);require(raw['video']['sha256']==entry['video_sha256'],'Pose/video binding')
    require(raw['provenance']==entry['identity_provenance'],'Full frozen identity provenance')
    validate_pose(raw)
    require(raw['extraction']=={'start':0,'end':None,'stride':1},'Whole141 extraction')
    require(raw['provenance']['script_sha256'] in ('04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f','b0eb01e8a0d24049cff8880dc3f356a177ada760cc919a31cfbd11ee7f82fa89'),'Unregistered historical script')
    if entry['id']=='source05':
        ex=read(ROOT/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')
        require(ex['passed'] is True and ex['source_sha256']==entry['video_sha256'] and ex['frames']==141,'Historical source opening exception')
    return video,pose,raw
def validate_pose(raw):
    require(raw['schema']=='h3_cpu_pose_v1','Pose schema')
    v=raw['video'];require([v['width'],v['height'],v['container_frame_count'],v['fps']]==[1312,736,141,24],'Pose geometry/timebase')
    require(len(raw['frames'])==141,'Frame count')
    for i,row in enumerate(raw['frames']):
        require(row['frame']==i and math.isfinite(row['time_s']) and abs(row['time_s']-i/24)<1e-9,'Frame/time sequence')
        selected=row['selected_person'];require(selected is None or type(selected) is int and 0<=selected<len(row['persons']),'Selected person')
        for person in row['persons']:
            xy=person['coco17_xy'];sc=person['coco17_score'];require(len(xy)==17 and len(sc)==17,'COCO17 shape')
            require(all(len(x)==2 and all(math.isfinite(z) for z in x) for x in xy) and all(math.isfinite(x) for x in sc),'Nonfinite keypoints/scores')
def online_pending():
    roots=['timing_auto_controller_r27_20261017','timing_auto_fresh_r32_20261017']
    for name in roots:
        root=Path('/data5/researcher/h3_runs')/name
        for request in (root/'audit/observations').glob('*/request.json'):
            response=request.parent/'response.json'
            if not response.exists():
                registry=root/'processes/service.json'
                if registry.exists():
                    rec=read(registry);pid=rec.get('pid')
                    if isinstance(pid,int) and Path('/proc',str(pid)).exists():return True
    return False
