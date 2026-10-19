"""One immutable R12 endpoint, GPU3 instead of GPU2; zero DiT calls."""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
R12 = Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
UUID = 'GPU-REDACTED'
DECODER = R12 / 'scripts/decode_x0.py'
SOURCE = R12 / 'audit/x0/r12_s05_native_observer/x0_step010.pt'
OLD_RECORD = R12 / 'analysis/pose/x0_decoded/x0_step010.json'
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot():
    return {key: subprocess.check_output(args, text=True).strip() for key, args in {
        'gpu': ['nvidia-smi', '--id=' + UUID, '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
        'compute': ['nvidia-smi', '--id=' + UUID, '--query-compute-apps=pid', '--format=csv,noheader,nounits'],
    }.items()}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'bridge.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record_path = ROOT / 'execution.json'
        if record_path.exists():
            raise RuntimeError('Execution already exists; inspect before any retry')
        assert sha(DECODER) == '799e64e1d2e1dab3582fe4600fea810c388facbab447fd0887dc51f4a1494014'
        assert sha(SOURCE) == '4e0ad90ebf903721ae488d8220524fe07dcf646bdf5c843cf634ae169755d56c'
        old = json.loads(OLD_RECORD.read_text())
        assert old['status'] == 'complete'
        assert old['decoded_tensor_sha256'] == 'b909923b104228887a7678828422c871bed60470fb565f15ff81024f84474f69'
        assert old['preencode_rgb24_sha256'] == '6e2d3554a6446bfbf3cf1f3b0ea064981dc8fec528ff904a6af1b53519a9d2aa'
        before = snapshot()
        assert not before['compute']
        fields = [s.strip() for s in before['gpu'].split(',')]
        assert fields[0] == UUID and int(fields[1]) <= 64 and int(fields[2]) == 0
        all_compute = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader'], text=True)
        for line in all_compute.splitlines():
            gpu, pid = [v.strip() for v in line.split(',')]
            proc = Path('/proc') / pid
            if proc.exists() and proc.stat().st_uid == os.getuid():
                assert pid == '53576' and gpu == 'GPU-REDACTED'
                assert proc.joinpath('stat').read_text().split(') ', 1)[1].split()[19] == '2618789964'
        output = ROOT / 'archived_native010_gpu3.mp4'
        args = [PYTHON, '-u', str(DECODER), str(SOURCE), '--core', '/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI',
                '--runtime-deps', '/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',
                '--vae', '/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors',
                '--expected-vae-sha256', '7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522',
                '--gpu-uuid', UUID, '--output', str(output)]
        record = {'status': 'running', 'started_unix': time.time(), 'NFE': 0, 'DiT_started': False,
                  'before': before, 'command': args, 'decoder_sha256': sha(DECODER),
                  'input_sha256': sha(SOURCE), 'old_record_sha256': sha(OLD_RECORD)}
        def save():
            record_path.write_text(json.dumps(record, indent=2) + '\n')
        save()
        env = os.environ.copy()
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[name] = '4'
        env['CUDA_VISIBLE_DEVICES'] = ''
        process = None
        try:
            with (ROOT / 'decode.log').open('x') as log:
                process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                record['child_pid'] = process.pid
                record['child_uid'] = Path('/proc') .joinpath(str(process.pid)).stat().st_uid
                record['child_start_ticks'] = Path('/proc', str(process.pid), 'stat').read_text().split(') ', 1)[1].split()[19]
                save()
                record['exit_code'] = process.wait(timeout=180)
            assert record['exit_code'] == 0
            current = json.loads(output.with_suffix('.json').read_text())
            assert current['status'] == 'complete' and current['snapshot_sha256'] == sha(SOURCE)
            log_text = (ROOT / 'decode.log').read_text()
            assert 'retrying with tiled VAE' not in log_text and 'OutOfMemoryError' not in log_text
            keys = ('decoded_tensor_sha256', 'preencode_rgb24_sha256', 'preencode_rgb24_frame_sha256', 'decoded_dtype', 'decoded_shape', 'output_sha256')
            record['equal_to_original_gpu2'] = {key: current[key] == old[key] for key in keys}
            assert all(record['equal_to_original_gpu2'].values())
            assert sha(output) == current['output_sha256']
            record['status'] = 'complete'
        except BaseException as error:
            record['status'] = 'failed'
            record['error'] = repr(error)
            raise
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            record['after'] = snapshot()
            record['child_absent'] = process is None or not Path('/proc', str(process.pid)).exists()
            record['finished_unix'] = time.time()
            record['wall_seconds'] = record['finished_unix'] - record['started_unix']
            save()
        assert record['child_absent'] and not record['after']['compute']
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
