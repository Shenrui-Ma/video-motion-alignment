"""Finalize one R8 intake; reuse pose only after exact final replay."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r8 as consumer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
R7=Path('/Users/researcher/DevProjects/h3-timing-normal-replay-r7-20261016/analysis/pose')
REMOTE=Path('/data5/researcher/h3_runs/timing_normal_feedback_r8_20261016')
BASE=Path('/data5/researcher/h3_runs/timing_normal_replay_r7_20261016')
RUN='r8_s05_normal_feedback'
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
STEMS=['x0_step005','x0_step006','x0_step007','x0_step008','x0_step009','x0_step010','x0_step015','x0_step019','sampler_final']
SHARED=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def normalize(graph):
    graph=json.loads(json.dumps(graph));del graph['50']
    for node in graph.values():
        for name in ('run_id','audit_dir','source_audit_dir','output_dir','filename_prefix'):
            node.get('inputs',{}).pop(name,None)
    return graph


def main():
    with (HERE/'finalizer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (HERE/'coordinator.lock').open('a') as intake_lock:
            fcntl.flock(intake_lock,fcntl.LOCK_EX)
            p=HERE/'pilot'/(RUN+'_provenance')
            manifest=json.loads((p/'intake_manifest.json').read_text())
            assert consumer.digest(HERE/'raw'/manifest['relative_video'])==manifest['video_sha256']
        with SHARED.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            subprocess.run([sys.executable,str(HERE/'check_native_replay_local.py')],check=True)
            subprocess.run([sys.executable,str(HERE/'check_feedback_audit.py')],check=True)
            a=json.loads((R7/'pilot/r7_s05_normal_native_x0_provenance/config.json').read_text())
            b=json.loads((p/'config.json').read_text())
            graph={'outside_actuator_and_admin_equal':normalize(a)==normalize(b),
                   'model_condition_connections_equal':all(a['50']['inputs'][k]==b['50']['inputs'][k] for k in ('model','positive'))}
            graph['passed']=all(graph.values());consumer.save(HERE/'replication/graph_pair_gate.json',graph)
            tool=REMOTE/'scripts/compare_x0_snapshots.py';expected=consumer.digest(ROOT/'scripts/compare_x0_snapshots.py')
            actual=consumer.shell('H3_SERVER_A',['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(tool)]).strip()
            assert actual==expected
            out=REMOTE/'analysis/pose/replication/common_actual_tensors.json'
            command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(BASE/'audit/x0/r7_s05_normal_native_x0'),str(REMOTE/'audit/x0'/RUN),str(out),'--stems',*STEMS]
            print(consumer.shell('H3_SERVER_A',command),flush=True)
            consumer.copy_from('H3_SERVER_A',out,HERE/'replication/common_actual_tensors.json')
            local=json.loads((HERE/'replication/native_replay_local_gate.json').read_text())
            op=json.loads((HERE/'operator_execution_gate.json').read_text())
            tensors=json.loads((HERE/'replication/common_actual_tensors.json').read_text())
            prefix=next(row for row in tensors['rows'] if row['stem']=='x0_step005')
            gate={'run_id':RUN,'actual_input_all_off_rgb_gate':local['passed'],
                  'state_machine_gate':op['passed'],'actual_graph_gate':graph['passed'],
                  'all_common9_video_audio_tensors_equal':tensors['all_equal'],
                  'prefix_index5_video_audio_equal':all(t['equal'] for t in prefix['tensors'].values()),
                  'selected_known_normal_case':True,'route_indices':op['active_forward_indices_zero_based']}
            gate['passed']=all(gate[k] for k in ('actual_input_all_off_rgb_gate','state_machine_gate','actual_graph_gate','all_common9_video_audio_tensors_equal','prefix_index5_video_audio_equal'))
            gate['scope']='Negative-control preservation only; not correction efficacy or independent unseen specificity. Unknown observer states are not alignment success.'
            consumer.save(HERE/'replication/complete_replay_gate.json',gate)
        exact_final=local['checks']['all_decoded_rgb_and_frame_timing_equal'] and local['checks']['geometry_timebase']
        if exact_final:
            reference=R7/'replication/inherited_final_pose_reference.json'
            consumer.save(HERE/'replication/inherited_pose_reference.json',{'exact_final_rgb':True,'source':str(reference),'source_sha256':consumer.digest(reference),'early_pose_reference':str(R7/'early/compact_summary.json'),'early_pose_reference_sha256':consumer.digest(R7/'early/compact_summary.json'),'only_reuse_early_if_common_tensor_gate_passes':tensors['all_equal']})
        else:
            # No local heavy lock is held here; the consumer acquires it itself.
            subprocess.run([sys.executable,str(HERE/'consumer_r8.py'),'--run-id',RUN],check=True)
        result={'status':'complete','complete_replay_passed':gate['passed'],'new_final_pose_required':not exact_final,
                'run_id':RUN,'no_gpu_started':True,'completed_unix':time.time()}
        consumer.save(HERE/'finalizer_state.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        consumer.save(HERE/'finalizer_failure.json',{'error':repr(exc),'retained':True,'unix':time.time()})
        raise
