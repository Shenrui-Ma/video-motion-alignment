"""Frozen CPU DWPose and signed controller replay after recovery decoder exits."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
import common as c

def validate_context(context):
    c.require(context['schema']=='r53-final-observation-recovery-context-v1' and context['prior19_replayed_exact'] is True and context['original_request_sha256']==c.REQUEST_SHA and context['failure_inventory_sha256']==c.INVENTORY_SHA,'invalid recovery context')
    c.require(context['failure_audit_sha256']==c.AUDIT_SHA and context['frozen_producer_manifest_sha256']==c.PRODUCER_MANIFEST_SHA and context['x19_proof_sha256']==c.REPLAY_SHA and context['x19_sha256']==c.X19_SHA,'recovery context source binding differs')
    c.require(context['original_run_completed'] is False and context['GPU_arithmetic_unverified'] is True,'recovery completion provenance differs')
    c.require([r['index'] for r in context['prior19']]==list(range(19)),'recovery prefix must contain exactly prior19 in order')

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--context',type=Path,default=c.HERE/'CONTEXT.json');p.add_argument('--context-sha256',required=True);a=p.parse_args()
    directory=a.directory.resolve();c.require(directory.is_relative_to(c.HERE/'runs'),'run outside recovery')
    os.environ['CUDA_VISIBLE_DEVICES']='';t=c.frozen_runtime();b=t.bindings(external=True);context=c.read(a.context)
    c.require(c.sha(a.context)==a.context_sha256,'recovery context SHA differs');validate_context(context)
    released=c.read(directory/'DECODER_RELEASED.json');decoded=c.read(directory/'RECOVERY_DECODE.json')
    c.require(released['status']=='released' and released['RECOVERY_DECODE_sha256']==c.sha(directory/'RECOVERY_DECODE.json'),'decoder release proof differs')
    c.require(not t.alive(released['child']['process']),'recovery decoder remains alive')
    c.require(decoded['status']=='decoded_archived_Native019' and c.sha(decoded['decode_file'])==decoded['decode_sha256'] and c.sha(decoded['video_file'])==decoded['video_sha256'],'recovered video evidence differs')
    lock=Path(t.read_json(c.PRODUCER/'configs/protocol.json')['resources']['CPU_lock']);lock.parent.mkdir(parents=True,exist_ok=True)
    pose_dir=directory/'pose';pose_dir.mkdir(exist_ok=False);started=time.monotonic()
    with lock.open('a') as handle:
        while True:
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()-started>600:raise TimeoutError('shared CPU pose lock unavailable')
                time.sleep(.3)
        wait=time.monotonic()-started;started=time.monotonic()
        try:
            command=[sys.executable,b['old_root']+'/scripts/pose_probe.py','--video',str(directory/'native.mp4'),'--output-dir',str(pose_dir),'--aux-root',b['aux_root'],'--threads','4','--stride','1']
            subprocess.run(command,check=True,timeout=240,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'))
            pose=pose_dir/'native.pose.json';raw=c.read(pose)
            c.require(raw['video']['sha256']==c.sha(directory/'native.mp4') and raw['video']['fps']==24 and raw['video']['width']==1312 and raw['video']['height']==736 and raw['video']['container_frame_count']==141 and [f['frame'] for f in raw['frames']]==list(range(141)),'recovery pose source/geometry differs')
            observer_path=directory/'observer.json'
            subprocess.run([sys.executable,str(c.PRODUCER/'scripts/scan_current_pose.py'),'--source',str(c.PRODUCER/'configs/source.pose.json'),'--pose',str(pose),'--index','19','--output',str(observer_path)],check=True,timeout=max(1,240-(time.monotonic()-started)))
        finally:fcntl.flock(handle,fcntl.LOCK_UN)
    measurement_record={'schema':'r53-recovery-measurement-v1','status':'complete','physical_index':19,'original_request_sha256':c.REQUEST_SHA,'recovery_decode_sha256':c.sha(directory/'RECOVERY_DECODE.json'),'observer_sha256':c.sha(observer_path),'pose_sha256':c.sha(pose),'original_run_completed':False}
    response_sha=c.write_new(directory/'RECOVERY_MEASUREMENT.json',measurement_record)
    sys.path.insert(0,str(c.PRODUCER/'extensions'))
    from H3AutomaticWindowRouter.selector import Controller
    policy=Controller();items=c.inventory();prefix=[]
    for row in context['prior19']:
        request_path=c.archived(row['request_relative'],items);response_path=c.archived(row['response_relative'],items);observer_path_old=c.archived(row['observer_relative'],items)
        c.require(c.sha(request_path)==row['request_sha256'] and c.sha(response_path)==row['response_sha256'] and c.sha(observer_path_old)==row['observer_sha256'],'prefix recovery context differs from archive')
        t.validate_response(c.read(response_path),c.read(request_path),row['request_sha256'])
        measurement={'status':'complete','observer':c.read(observer_path_old),'response_sha256':row['response_sha256'],'request_sha256':row['request_sha256']}
        decision=policy.select(row['index'],measurement);c.require(decision==row['expected_decision'],'prior19 controller state differs')
        prefix.append({'index':row['index'],'chosen_full':decision['chosen_full'],'exact':True})
    observation=c.read(observer_path);measurement={'status':'complete','observer':observation,'response_sha256':response_sha,'request_sha256':c.REQUEST_SHA}
    final=policy.select(19,measurement)
    result={'schema':'r53-final-signed-decision-recovery-v1','status':'requires_one_Full_model_forward' if final['chosen_full'] else 'OFF_final_Euler_update_required','original_run_completed':False,'context_sha256':c.sha(a.context),'producer_manifest_sha256':c.PRODUCER_MANIFEST_SHA,'prior19_replay':prefix,'decision19':final,'current_observation_sha256':c.sha(observer_path),'recovery_measurement_sha256':response_sha,'x19_file':context['x19_file'],'x19_sha256':context['x19_sha256'],'Native019_endpoint_sha256':c.ENDPOINT_SHA,'GPU_arithmetic_unverified':True,'final_video_exists':False,'pose_lock_wait_seconds':wait,'pose_and_metric_seconds':time.monotonic()-started,'scope':'Actual final decision from recovered Native019. ON needs a Full same-input prediction; OFF still needs final Euler arithmetic validation and final decoding.'}
    c.write_new(directory/'DECISION19.json',result);print(json.dumps({'status':result['status'],'decision19':final,'file':str(directory/'DECISION19.json')}))
if __name__=='__main__':main()
