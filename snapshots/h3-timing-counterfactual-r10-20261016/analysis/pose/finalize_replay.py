"""Bounded R10 exact replay acceptance. No GPU or automatic DWPose fallback."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r10 as consumer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
REMOTE=Path('/data5/researcher/h3_runs/timing_counterfactual_r10_20261016')
PARENT=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016')
RUN='r10_s05_fixed_full_probe'
SHARED=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def main():
    with (HERE/'finalizer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        consumer.save(HERE/'finalizer_state.json',{'status':'waiting_for_actual_success','run_id':RUN,'started_unix':time.time(),'automatic_pose_fallback':False})
        subprocess.run([sys.executable,str(HERE/'consumer_r10.py'),'--run-id',RUN,'--wait','--intake-only'],check=True)
        prov=HERE/'pilot'/(RUN+'_provenance')
        if not (prov/'intake_manifest.json').is_file():raise ValueError('No admitted actual success; keep retained failure')
        with SHARED.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            local_tool=ROOT/'scripts/compare_parent.py';sha=consumer.digest(local_tool)
            remote_tool=REMOTE/'scripts/compare_parent.py'
            actual=consumer.shell('H3_SERVER_A',['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(remote_tool)]).strip()
            if actual!=sha:raise ValueError('Official comparator source differs from local archive')
            old_manifest=PARENT/'audit/x0/r3_s05_full_6to14/manifest.json'
            expected={str(REMOTE/'audit/parent_x0_manifest.json'):consumer.digest(old_manifest),
                      str(REMOTE/'audit/parent_full_conditioning.json'):consumer.digest(PARENT/'analysis/pose/pilot/r3_s05_full_6to14_provenance/conditioning.json')}
            code='''import fcntl,hashlib,json,os,runpy,sys
from pathlib import Path
expected=json.loads(sys.argv[1]);script=sys.argv[2];root=sys.argv[3]
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for path,sha in expected.items():
  assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,'Archived parent evidence mismatch '+path
 os.environ['CUDA_VISIBLE_DEVICES']=''
 import torch
 torch.set_num_threads(1)
 sys.argv=[script,'--root',root]
 runpy.run_path(script,run_name='__main__')
'''
            result=consumer.shell('H3_SERVER_A',['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','/home/researcher/miniconda3/envs/comfyui/bin/python','-c',code,json.dumps(expected),str(remote_tool),str(REMOTE)])
            (HERE/'official_compare.stdout.json').write_text(result)
            consumer.copy_from('H3_SERVER_A',REMOTE/'analysis/parent_pair_check.json',HERE/'replication/parent_pair_check.json')
            subprocess.run([sys.executable,str(HERE/'check_rgb_inputs.py')],check=True)
            rgb=json.loads((HERE/'replication/native_replay_local_gate.json').read_text())
            parent=json.loads((HERE/'replication/parent_pair_check.json').read_text())
            gate={'status':'complete','run_id':RUN,'passed':parent['passed'] and rgb['passed'],
                  'official_comparator_sha256':sha,'parent_evidence_sha256':expected,
                  'parent_tensor_gate':parent,'rgb_input_gate_path':str(HERE/'replication/native_replay_local_gate.json'),
                  'matching_decoded_rgb_frames':rgb['matching_rgb_frame_count'],'NFE':29,'euler_updates':20,
                  'no_gpu_started':True,'new_pose_extraction':False,'completed_unix':time.time(),
                  'interpretation':'Exact replay permits inherited parent final pose, not new efficacy evidence. No all20 parent intermediate equality claim.'}
            if gate['passed']:
                source=PARENT/'analysis/pose/pilot'
                files=[source/'r3_s05_full_6to14_00001_.pose.json']+[source/f'r3_s05_full_6to14_00001_.threshold{t}.timing.json' for t in ['0.3','0.5']]
                inherited={'parent':'r3_s05_full_6to14','new':RUN,'reason':'All141 decodedRGB/timebase equal, actual inputs/noise and archived selected tensors/final exact','files':{str(f):consumer.digest(f) for f in files},'new_sample':False}
                consumer.save(HERE/'replication/inherited_final_pose.json',inherited)
            else:
                gate['interpretation']='Replay difference found. Pause causal interpretation; no model, threshold or automatic DWPose changes.'
            consumer.save(HERE/'replication/complete_replay_gate.json',gate)
            if gate['passed']:
                subprocess.run([sys.executable,str(HERE/'summarize_probe.py')],check=True)
            consumer.save(HERE/'finalizer_state.json',{'status':'complete' if gate['passed'] else 'difference_requires_parent_review','passed':gate['passed'],'automatic_pose_fallback':False})
            print(json.dumps({'run_id':RUN,'passed':gate['passed'],'rgb_frames_equal':rgb['matching_rgb_frame_count']}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        consumer.save(HERE/'finalizer_failure.json',{'error':repr(exc),'retained':True,'no_automatic_science_changes':True,'unix':time.time()})
        raise
