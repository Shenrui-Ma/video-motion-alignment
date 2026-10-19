"""Sequential offline VAE probes on one admitted idle GPU; no DiT is loaded."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--gpu-uuid', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_]+', args.run_id):
        raise ValueError('invalid run id')
    root = Path(__file__).resolve().parents[1]
    source = root/'audit/x0'/args.run_id
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['run_id'] != args.run_id:
        raise ValueError('capture must be complete before decoding')
    destination = root/'outputs/x0_decoded'/args.run_id
    destination.mkdir(parents=True, exist_ok=True)
    record_path = destination/'batch.json'
    if record_path.exists():
        raise FileExistsError(record_path)
    record = {'run_id': args.run_id, 'pid': os.getpid(), 'uid': os.getuid(),
              'gpu_uuid': args.gpu_uuid, 'started_unix': time.time(),
              'status': 'running', 'children': []}
    def write():
        tmp = record_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(record, indent=2)+'\n')
        tmp.replace(record_path)
    write()
    env = dict(os.environ, OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
               OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4', PYTHONDONTWRITEBYTECODE='1')
    try:
        for stem in ('sampler_final', 'x0_step019', 'x0_step005', 'x0_step010', 'x0_step015'):
            command = [sys.executable, str(root/'scripts/decode_x0.py'), str(source/(stem+'.pt')),
                       '--core', '/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI',
                       '--runtime-deps', '/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',
                       '--vae', '/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors',
                       '--expected-vae-sha256', '7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522',
                       '--gpu-uuid', args.gpu_uuid, '--output', str(destination/(stem+'.mp4'))]
            child_record = {'snapshot': stem, 'command': command, 'started_unix': time.time()}
            record['children'].append(child_record)
            with (destination/(stem+'.log')).open('xb') as log:
                child = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                child_record['pid'] = child.pid
                write()
                try:
                    code = child.wait(timeout=600)
                except BaseException:
                    child.terminate()
                    try:
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                    raise
            child_record.update(exit_code=code, finished_unix=time.time())
            write()
            if code:
                raise RuntimeError(f'{stem} decode exited {code}; retained log, no further snapshots run')
            print(json.dumps({'completed': stem, 'run_id': args.run_id}), flush=True)
        record['status'] = 'complete'
    except BaseException as exc:
        record.update(status='failed', error=repr(exc))
        raise
    finally:
        record['finished_unix'] = time.time()
        record['gpu_after'] = subprocess.check_output(['nvidia-smi', '-i', args.gpu_uuid,
            '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader'], text=True).strip()
        record['compute_pids_after'] = subprocess.check_output(['nvidia-smi', '-i', args.gpu_uuid,
            '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
        write()


if __name__ == '__main__':
    main()
