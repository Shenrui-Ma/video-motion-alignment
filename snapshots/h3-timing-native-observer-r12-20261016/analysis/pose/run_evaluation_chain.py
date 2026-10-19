"""One CPU-only R12 consumer: exact success, integrity gates, frozen pose."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r12 as consumer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REMOTE = Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
R3 = Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016')
R10 = Path('/Users/researcher/DevProjects/h3-timing-counterfactual-r10-20261016')
RUN = 'r12_s05_native_observer'
SHARED = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def integrity():
    tool = ROOT/'scripts/compare_parent.py'
    wanted = consumer.digest(tool)
    expected = {
        str(REMOTE/'scripts/compare_parent.py'): wanted,
        str(REMOTE/'audit/parent_x0_manifest.json'): consumer.digest(R3/'audit/x0/r3_s05_full_6to14/manifest.json'),
        str(REMOTE/'audit/parent_full_conditioning.json'): consumer.digest(R3/'analysis/pose/pilot/r3_s05_full_6to14_provenance/conditioning.json'),
    }
    recovered_path = HERE/'replication/recovered_official_compare.json'
    recovered_result = ''
    if recovered_path.is_file():
        recovered = json.loads(recovered_path.read_text())
        assert recovered['passed']
        files = recovered['remote_files']
        assert files['comparator']['sha256'] == wanted
        assert consumer.digest(HERE/'replication/parent_pair_check.json') == files['official_result']['sha256']
        assert consumer.digest(HERE/'pilot'/(RUN+'_provenance/router_audit.json')) == files['router_audit']['sha256']
        expected.update({item['path']:item['sha256'] for item in files.values()})
        recovered_result = files['official_result']['path']
    code = '''import fcntl,hashlib,json,os,runpy,sys
from pathlib import Path
expected=json.loads(sys.argv[1]);root=Path(sys.argv[2]);script=str(root/'scripts/compare_parent.py');recovered=sys.argv[3]
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for path,sha in expected.items():
  assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,'Comparator or parent evidence mismatch '+path
 if recovered:
  print(Path(recovered).read_text())
 else:
  os.environ['CUDA_VISIBLE_DEVICES']=''
  import torch
  torch.set_num_threads(1)
  sys.argv=[script,'--root',str(root)]
  runpy.run_path(script,run_name='__main__')
'''
    output = consumer.shell('H3_SERVER_A', ['env', 'CUDA_VISIBLE_DEVICES=', 'OMP_NUM_THREADS=1',
        'MKL_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', '/home/researcher/miniconda3/envs/comfyui/bin/python',
        '-c', code, json.dumps(expected), str(REMOTE), recovered_result])
    (HERE/'official_compare.stdout.json').write_text(output)
    consumer.copy_from('H3_SERVER_A', REMOTE/'analysis/parent_pair_check.json', HERE/'replication/parent_pair_check.json')
    result = json.loads((HERE/'replication/parent_pair_check.json').read_text())
    assert result['passed']
    subprocess.run([sys.executable, str(HERE/'check_capture_inventory.py'), '--run-id', RUN], check=True)
    capture = json.loads((HERE/'replication'/RUN/'capture_inventory.json').read_text())
    assert capture['passed'] and len(capture['rows']) == 9
    current = HERE/'pilot'/(RUN+'_provenance')
    c = json.loads((current/'conditioning.json').read_text())
    n = json.loads((current/'noise.json').read_text())
    rows = {}
    for label, folder in {
        'r3_native': R3/'analysis/pose/pilot/r3_s05_native_provenance',
        'r3_full': R3/'analysis/pose/pilot/r3_s05_full_6to14_provenance',
        'r10_full_probe': R10/'analysis/pose/pilot/r10_s05_fixed_full_probe_provenance',
    }.items():
        old = json.loads((folder/'conditioning.json').read_text())
        oldn = json.loads((folder/'noise.json').read_text())
        checks = {key: c[key] == old[key] for key in ['prompt', 'input_video', 'native_vae_calls',
            'qwen_presentation', 'tokenization_before_vision_expansion', 'conditioning_embedding',
            'token_tags', 'target_latent_shapes', 'packed_layout']}
        checks.update(pair_snapshot_actual=c['pair_snapshot']['actual']==old['pair_snapshot']['actual'],
            actual_noise_streams=n['actual_noise_streams']==oldn['actual_noise_streams'],
            noise_signature=n['signature']==oldn['signature'])
        rows[label] = {'checks': checks, 'passed': all(checks.values()),
            'source_hashes': {f:consumer.digest(folder/f) for f in ['conditioning.json','noise.json']}}
    pair = {'all_passed': all(r['passed'] for r in rows.values()), 'rows': rows,
        'current_hashes': {f: consumer.digest(current/f) for f in ['conditioning.json','noise.json']}}
    consumer.save(HERE/'actual_input_noise_pair.json', pair)
    assert pair['all_passed']
    r10_gate = json.loads((R10/'analysis/pose/replication/complete_replay_gate.json').read_text())
    assert r10_gate['passed']
    gate = {'passed': True, 'run_id': RUN, 'official_comparator_sha256': wanted,
        'parent_evidence_hashes': expected, 'official_result': result,
        'actual_input_noise_pair': str(HERE/'actual_input_noise_pair.json'),
        'strict_eight_capture_inventory': str(HERE/'replication'/RUN/'capture_inventory.json'),
        'prefix5_equals_r3_full': True,
        'prefix5_equals_r10_via_verified_r3_equality': True,
        'r10_complete_gate_sha256': consumer.digest(R10/'analysis/pose/replication/complete_replay_gate.json'),
        'final_match_to_full_required': False, 'new_gpu_started': False}
    consumer.save(HERE/'replication/complete_integrity_gate.json', gate)


def main():
    with (HERE/'serial_chain.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        consumer.save(HERE/'serial_chain_state.json', {'status':'waiting_for_formal_history',
            'run_id':RUN, 'started_unix':time.time(), 'GPU_started':False})
        subprocess.run([sys.executable,str(HERE/'consumer_r12.py'),'--run-id',RUN,'--wait','--intake-only'],check=True)
        assert (HERE/'pilot'/(RUN+'_provenance/intake_manifest.json')).is_file(), 'No admitted success'
        with SHARED.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            integrity()
        consumer.save(HERE/'serial_chain_state.json', {'status':'integrity_passed_waiting_pose_lock','run_id':RUN})
        subprocess.run([sys.executable,str(HERE/'consumer_r12.py'),'--run-id',RUN],check=True)
        assert (HERE/'pilot'/(RUN+'_provenance/archive_manifest.json')).is_file(), 'No measured output'
        with SHARED.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            subprocess.run([sys.executable,str(HERE/'complete_r12.py')],check=True)
        consumer.save(HERE/'serial_chain_state.json', {'status':'metrics_and_controls_complete',
            'run_id':RUN,'completed_unix':time.time(),'fixed_frame_quality_pending':True,'GPU_started':False})


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        consumer.save(HERE/'serial_chain_failure.json', {'error':repr(exc),'retained':True,
            'unix':time.time(),'automatic_science_changes':False})
        raise
