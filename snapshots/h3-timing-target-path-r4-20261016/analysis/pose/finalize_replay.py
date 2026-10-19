"""Serial CPU-only finalizer; waits on the single already-running intake lock.

No model weights, pose model, GPU, or inference service is started. Completed
intake is required; transport retry does not reinterpret a science failure.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r4 as intake

HERE=Path(__file__).resolve().parent
HOST='H3_SERVER_B'
REMOTE=Path('/data3/researcher/h3_runs/timing_target_path_r4_20261016')
BASE=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016')
RUN='r4_s05_native_path_probe'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
STEMS=['x0_step005','x0_step010','x0_step015','x0_step019','sampler_final']


def final_gate(local,tensor):
    return {'baseline_run':'r2_s05_native','new_run':RUN,
            'local_input_rgb_native_operator_gate':local['passed'],
            'actual_common_video_audio_tensors_equal':tensor['all_equal'],
            'common_tensor_stems':STEMS,
            'passed':local['passed'] and tensor['all_equal'],
            'interpretation':'Exact same-host replay prerequisite only; not an independent efficacy sample. A mismatch is retained and forbids importing the old pose results as identical.',
            'no_new_pose_or_gpu':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:
        assert final_gate({'passed':True},{'all_equal':True})['passed']
        assert not final_gate({'passed':False},{'all_equal':True})['passed']
        assert not final_gate({'passed':True},{'all_equal':False})['passed']
        print(json.dumps({'self_test_passed':True,'all_gates_required':True,'no_network_or_gpu':True}));return
    with (HERE/'replay_finalizer.lock').open('a') as finalizer_lock:
        fcntl.flock(finalizer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # This does not start a second intake. Wait for its exclusive lock.
        with (HERE/'coordinator.lock').open('a') as intake_lock:
            fcntl.flock(intake_lock,fcntl.LOCK_EX)
            provenance=HERE/'pilot'/(RUN+'_provenance')
            path=provenance/'intake_manifest.json'
            if not path.is_file():raise ValueError('Single intake ended without admitted formal output')
            record=json.loads(path.read_text())
            assert record['run_id']==RUN
            assert intake.digest(HERE/'raw'/record['relative_video'])==record['video_sha256']
            subprocess.run([sys.executable,str(HERE/'check_native_replay_local.py')],check=True)
            tool=REMOTE/'scripts/compare_x0_snapshots.py'
            expected=intake.digest(HERE.parent.parent/'scripts/compare_x0_snapshots.py')
            actual=intake.shell(HOST,['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(tool)]).strip()
            assert expected==actual,'Remote comparison tool differs from archived source'
            target=REMOTE/'analysis/pose/replication/native_replay_actual_tensors.json'
            command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(BASE/'audit/x0/r2_s05_native'),str(REMOTE/'audit/x0'/RUN),str(target),'--stems',*STEMS]
            print(intake.shell(HOST,command),flush=True)
            local_target=HERE/'replication/native_replay_actual_tensors.json'
            intake.copy_from(HOST,target,local_target)
            local=json.loads((HERE/'replication/native_replay_local_gate.json').read_text())
            tensors=json.loads(local_target.read_text());result=final_gate(local,tensors)
            result['evidence_sha256']={name:intake.digest(HERE/'replication'/name) for name in ['native_replay_local_gate.json','native_replay_actual_tensors.json']}
            result['tensor_comparator_sha256']=expected
            intake.save(HERE/'replication/native_replay_complete_gate.json',result)
            intake.save(HERE/'replay_state.json',{'status':'complete','run_id':RUN,'passed':result['passed'],'no_new_pose_or_gpu':True})
            print(json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        intake.save(HERE/'replay_failure.json',{'error':repr(exc),'retained':True,'not_a_positive_replay_gate':True,'unix':time.time()})
        raise
