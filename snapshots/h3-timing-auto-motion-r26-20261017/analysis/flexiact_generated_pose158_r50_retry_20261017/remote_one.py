"""Extract one actual generated full158 video; all missing parents stay pending."""
import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import time
from contract import *


def execute(source, method, metric_path, mapping_path):
    protocol = read(HERE / 'PROTOCOL.json')
    require(method != 'native' or 'native_reuse' not in protocol, 'Native5 are reused through their original frozen receipts')
    require(source in protocol['source_order'] and method in protocol['methods'], 'fixed ten cases')
    check_freeze(protocol)
    helper = source_helper(protocol)
    if helper.online_pending(protocol):
        raise BlockingIOError('online observer priority')
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if helper.online_pending(protocol):
            raise BlockingIOError('online observer priority')
        metric_path, mapping_path = Path(metric_path), Path(mapping_path)
        if not metric_path.exists() or not mapping_path.exists():
            return {'status': 'pending', 'source_id': source, 'pair_id': protocol['pairs'][source]['pair_id'], 'method': method, 'reason': 'actual metric/release parent unavailable'}
        metric, mapping = read(metric_path), read(mapping_path)
        validate_metadata(protocol, source, method, metric, mapping)
        validate_paths(protocol, method, metric_path, mapping_path, metric)
        case_files = metric_path.parent / 'CASE_FILES.json'
        if not case_files.exists():
            return {'status': 'pending', 'source_id': source, 'method': method, 'reason': 'postrun case completion unavailable'}
        inventory = read(case_files)
        for path in (metric_path, mapping_path):
            rel = str(path.relative_to(metric_path.parent))
            require(inventory[rel] == sha(path), 'postrun case inventory identity')
        required = {str(metric_path): sha(metric_path), str(mapping_path): sha(mapping_path), str(case_files): sha(case_files), metric['full158_output']: metric['full158_output_sha256'], metric['edited49']: metric['edited49_sha256'], metric['original_source']: metric['original_source_sha256'], metric['target_image']: metric['target_sha256']}
        for path, digest in required.items():
            require(sha(path) == digest, 'actual bound input SHA')
        for path, digest in protocol['frozen_external'].items():
            require(sha(path) == digest, 'frozen pose script/model')
        dest = HERE / 'records' / (method + '_' + source)
        require(not dest.exists(), 'prior phase exists; explicit review required')
        dest.mkdir(parents=True)
        shutil.copyfile(metric_path, dest / 'METRIC_INPUTS.json')
        shutil.copyfile(mapping_path, dest / 'release49.mapping.json')
        shutil.copyfile(case_files, dest / 'PARENT_CASE_FILES.json')
        binding = {'pair_id': protocol['pairs'][source]['pair_id'], 'source_id': source, 'method': method, 'run_id': metric['run_id'], 'actual_inputs': required, 'metric_inputs_path': str(metric_path), 'release49_mapping_path': str(mapping_path), 'full158_path': metric['full158_output'], 'full158_sha256': metric['full158_output_sha256'], 'code_freeze_sha256': sha(HERE / 'FREEZE.json')}
        save(dest / 'INPUT_BINDING.json', binding)
        script = next(p for p in protocol['frozen_external'] if p.endswith('/pose_probe.py'))
        command = [sys.executable, script, '--video', metric['full158_output'], '--output-dir', str(dest), '--threads', '4', '--stride', '1']
        start = time.monotonic()
        with (dest / 'pose.log').open('x') as log:
            proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4'), timeout=protocol['timeout_seconds'])
        require(proc.returncode == 0, 'pose extraction failed; retain phase')
        pose = dest / (Path(metric['full158_output']).stem + '.pose.json')
        raw = helper.validate_pose(read(pose), metric['full158_output_sha256'], protocol)
        validate_pose_provenance(protocol, raw)
        provenance = {'pair_id': binding['pair_id'], 'source_id': source, 'method': method, 'command': command, 'elapsed_seconds': time.monotonic() - start, 'pose_path': str(pose), 'pose_sha256': sha(pose), 'raw_provenance': raw['provenance'], 'statistics': raw['statistics'], 'input_binding_sha256': sha(dest / 'INPUT_BINDING.json'), 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'protocol_sha256': sha(HERE / 'PROTOCOL.json')}
        save(dest / 'PROVENANCE.json', provenance)
        for path, digest in required.items():
            require(sha(path) == digest, 'actual input changed during extraction')
        check_freeze(protocol)
        save(dest / 'COMPLETE.json', {'status': 'complete', 'pair_id': binding['pair_id'], 'source_id': source, 'method': method, 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'files': {p.name: sha(p) for p in dest.iterdir() if p.is_file()}})
        return {'status': 'complete', 'source_id': source, 'method': method, 'pair_id': binding['pair_id'], 'pose_path': str(pose), 'pose_sha256': sha(pose), 'elapsed_seconds': provenance['elapsed_seconds']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--method', required=True)
    parser.add_argument('--metric-inputs', required=True)
    parser.add_argument('--mapping', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.source, args.method, args.metric_inputs, args.mapping), allow_nan=False))
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
        raise SystemExit(75)
