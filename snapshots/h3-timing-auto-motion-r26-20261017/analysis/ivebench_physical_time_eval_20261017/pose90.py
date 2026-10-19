"""CPU-only generated90 consumer with exact released-case provenance."""
import argparse,fcntl,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from evaluate90 import P, valid_view
HERE=Path(__file__).resolve().parent
NATIVE=Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017')
AUTO=Path('/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017')
SOURCE=NATIVE/'analysis/source_pose90'
AUX=Path('/data3/researcher/ComfyUI-H3/custom_nodes/comfyui_controlnet_aux')
LOCK=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def require(ok,msg):
    if not ok:raise ValueError(msg)
def save(p,j):
    with Path(p).open('x') as f:json.dump(j,f,indent=2,allow_nan=False);f.write('\n')
def frozen():
    for rel,digest in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==digest,'changed frozen file '+rel)
def bound(row):
    p=Path(row['file']);require(p.is_absolute() and sha(p)==row['sha256'],'bound file changed');return p

def validate_metadata(row,pair,method):
    case=next(c for c in P['cases'] if c['pair_id']==pair)
    require(row['pair_id']==pair and set(row['edited'])=={method},'pair or method differs')
    require(row['source_prepared_video']['sha256']==case['video_sha256'],'prepared source differs')
    require(row['source_preparation_record']['sha256']==case['provenance_sha256'],'source preparation differs')
    require(row['score_frame_indices']==list(range(case['effective_frames'])),'effective prefix differs')
    return case

def validate_case(path,pair,method):
    path=Path(path).resolve();root=NATIVE if method=='native' else AUTO
    require(path.is_relative_to(root/'analysis/postrun') and path.name=='METRIC_INPUTS.json','outside assigned case consumer')
    row=read(path);case=validate_metadata(row,pair,method);files=read(path.parent/'CASE_FILES.json')
    require({str(p.relative_to(path.parent)) for p in path.parent.rglob('*') if p.is_file()}==set(files)|{'CASE_FILES.json'},'case inventory membership differs')
    for rel,digest in files.items():require(sha(path.parent/rel)==digest,'case inventory content differs')
    summary=read(path.parent/'SUMMARY.json');require(summary['passed'] is True and summary['source_id']==pair and summary['metric_inputs_sha256']==sha(path) and summary['padding_evaluated'] is False and summary['decoded_frame_md5_equal'] is True,'case completion proof differs')
    for role in ['source_original','source_prepared_video','source_score_video','source_preparation_record']:bound(row[role])
    provenance=read(bound(row['source_preparation_record']))
    require(provenance['selection_sha256']==P['selection_sha256'] and provenance['input_to_original_frame']==row['input_to_original_frame'] and provenance['effective_frame_count']==case['effective_frames'],'source selection or frame map differs')
    edit=row['edited'][method]
    for value in edit.values():bound(value)
    generation=read(bound(edit['generation_record']));full=bound(edit['full_video'])
    require(generation['source_id']==pair and generation['method']==method and generation['geometry']==P['geometry'] and generation['full_video']==edit['full_video'] and generation['source_prepared_video']==row['source_prepared_video'] and generation['source_provenance']==row['source_preparation_record'],'generation binding differs')
    for field in ['graph','history','job']:bound(generation[field])
    consumer=root/'analysis/postrun';binding=read(consumer/'BINDING.json');freeze=read(consumer/'FREEZE.json')
    require(binding['approved_for_consumer_start'] is True and binding['consumer_freeze_sha256']==sha(consumer/'FREEZE.json') and binding['producer_manifest_sha256']==generation['producer_manifest_sha256'],'actual consumer approval differs')
    for rel,digest in freeze['files'].items():require(sha(consumer/rel)==digest,'consumer changed')
    return case,row,full,{'metric_inputs_path':str(path),'metric_inputs_sha256':sha(path),'case_files_sha256':sha(path.parent/'CASE_FILES.json'),'consumer_freeze_sha256':sha(consumer/'FREEZE.json'),'consumer_binding_sha256':sha(consumer/'BINDING.json'),'generation_record_sha256':edit['generation_record']['sha256'],'release_record_sha256':edit['release_record']['sha256']}

def validate_pose(raw,digest,count):
    require(raw['video']['sha256']==digest,'pose video hash differs')
    require(raw['provenance']==P['expected_pose_provenance'],'pose runtime/model provenance differs')
    try:valid_view(raw,count,.3)
    except ValueError as exc:
        if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
    return raw

def online_pending():
    return any(p.exists() and not (p.parent/'response.json').exists() for p in (AUTO/'audit/observations').glob('*/request.json'))

def extract(pair,method,metric):
    frozen()
    if online_pending():raise BlockingIOError('online observer priority')
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if online_pending():raise BlockingIOError('online observer priority')
        case,row,full,binding=validate_case(metric,pair,method)
        require(sha(SOURCE/'pose_probe.py')==P['pose_script_sha256'],'pose script differs')
        for rel,digest in P['aux_files'].items():require(sha(AUX/rel)==digest,'pose model/code differs')
        dest=HERE/'records'/f'{method}_{pair}';dest.mkdir(parents=True,exist_ok=False)
        save(dest/'INPUT_BINDING.json',dict(binding,full_video=row['edited'][method]['full_video'],pair_id=pair,method=method,protocol_sha256=sha(HERE/'PROTOCOL.json')))
        shutil.copyfile(metric,dest/'METRIC_INPUTS.json')
        command=[sys.executable,str(SOURCE/'pose_probe.py'),'--aux-root',str(AUX),'--threads','4','--stride','1','--video',str(full),'--output-dir',str(dest)]
        start=time.monotonic()
        with (dest/'pose.log').open('x') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=300,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1'))
        require(result.returncode==0,'pose extraction failed; keep exact partial phase')
        pose=dest/(full.stem+'.pose.json');validate_pose(read(pose),sha(full),case['effective_frames']);validate_case(metric,pair,method);frozen()
        save(dest/'COMPLETE.json',{'status':'complete','pair_id':pair,'method':method,'pose_file':str(pose),'pose_sha256':sha(pose),'full_video_sha256':sha(full),'protocol_sha256':sha(HERE/'PROTOCOL.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'command':command,'cpu_seconds':time.monotonic()-start,'files':{p.name:sha(p) for p in dest.iterdir() if p.is_file()}})
        return read(dest/'COMPLETE.json')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pair',choices=[c['pair_id'] for c in P['cases']],required=True);ap.add_argument('--method',choices=P['methods'],required=True);ap.add_argument('--metric-inputs',required=True);a=ap.parse_args()
    try:r=extract(a.pair,a.method,a.metric_inputs)
    except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');return 75
    print(json.dumps({k:r[k] for k in ['status','pair_id','method','pose_sha256','cpu_seconds']}));return 0
if __name__=='__main__':raise SystemExit(main())
