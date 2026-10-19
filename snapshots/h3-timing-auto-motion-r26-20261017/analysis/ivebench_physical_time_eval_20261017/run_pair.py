"""Pair actual source90 with two completed generated90 records."""
import argparse,json,time
from pathlib import Path
from pose90 import *
from evaluate90 import evaluate

def generated(pair,method):
    folder=HERE/'records'/f'{method}_{pair}';receipt=read(folder/'COMPLETE.json')
    require(receipt['status']=='complete' and receipt['pair_id']==pair and receipt['method']==method and receipt['freeze_sha256']==sha(HERE/'FREEZE.json') and receipt['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'generated receipt differs')
    for rel,digest in receipt['files'].items():require(sha(folder/rel)==digest,'generated pose receipt content differs')
    binding=read(folder/'INPUT_BINDING.json');case,row,full,actual=validate_case(binding['metric_inputs_path'],pair,method)
    for field in actual:require(binding[field]==actual[field],'upstream receipt changed')
    pose=Path(receipt['pose_file']);require(pose.parent==folder and sha(pose)==receipt['pose_sha256'],'generated pose identity differs')
    return validate_pose(read(pose),sha(full),case['effective_frames']),receipt

def run(pair,output):
    frozen();case=next(c for c in P['cases'] if c['pair_id']==pair)
    require(sha(SOURCE/'PROTOCOL.json')==P['source_protocol_sha256'] and sha(SOURCE/'COMPLETE.json')==P['source_complete_sha256'],'actual source cache binding differs')
    sourcepath=Path(case['source_pose_path']);require(sha(sourcepath)==case['source_pose_sha256'],'source pose changed')
    source=validate_pose(read(sourcepath),case['video_sha256'],case['effective_frames'])
    native,nreceipt=generated(pair,'native');auto,areceipt=generated(pair,'auto');start=time.monotonic()
    result=evaluate(source,native,auto,pair)
    record={'pair_id':pair,'fixed_pair_denominator':5,'status':'pair_complete','result':result,'cpu_seconds':time.monotonic()-start,'protocol_sha256':sha(HERE/'PROTOCOL.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'source_pose_sha256':case['source_pose_sha256'],'generated_receipts':{'native':nreceipt,'auto':areceipt}}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);save(output,record)
    return {'pair_id':pair,'output':str(output),'sha256':sha(output),'cpu_seconds':record['cpu_seconds']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pair',choices=[c['pair_id'] for c in P['cases']],required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    if online_pending():raise SystemExit(75)
    try:
        with LOCK.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if online_pending():raise SystemExit(75)
            print(json.dumps(run(a.pair,a.output)))
    except BlockingIOError:raise SystemExit(75)
