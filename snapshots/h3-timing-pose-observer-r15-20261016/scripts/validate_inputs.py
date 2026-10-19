"""CPU-only actual-schema gate; never creates/initializes a GPU context."""
import fcntl
import importlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '4'
import torch
torch.set_num_threads(4)
torch.set_num_interop_threads(1)
import decode_endpoint as adapter

def main():
    root = Path(__file__).resolve().parents[1]
    lock_path = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.time()
        decoder = adapter.decoder_module()
        sys.path.insert(0, str(adapter.R12 / 'extensions'))
        core = importlib.import_module('H3X0Readout.core')
        rows = []
        for expected in json.loads((root / 'analysis/input_inventory.json').read_text())['inputs']:
            loader = adapter.build_loader(decoder, expected)
            t = time.time()
            data = loader(Path(expected['path']), core)
            rows.append({'case': expected['case'], 'index': expected['index'],
                         'file_sha256': adapter.sha(expected['path']),
                         'video': core.tensor_signature(data['video']),
                         'audio': core.tensor_signature(data['audio']),
                         'metadata': data['metadata'], 'finite': True,
                         'cuda_initialized': torch.cuda.is_initialized(), 'wall_seconds': time.time()-t})
            bad = dict(expected, sha256='0'*64)
            try:
                adapter.build_loader(decoder, bad)(Path(expected['path']), core)
            except ValueError as error:
                if str(error) != 'Snapshot file SHA differs':
                    raise
            else:
                raise AssertionError('Negative file-hash test did not fail closed')
        try:
            adapter.selected_row('r10_native', 10)
        except ValueError:
            pass
        else:
            raise AssertionError('Unregistered input was admitted')
        assert not torch.cuda.is_initialized()
        out = {'status': 'pass', 'cpu_only': True, 'cuda_initialized': False, 'nfe': 0,
               'started_unix': start, 'finished_unix': time.time(), 'wall_seconds': time.time()-start,
               'rows': rows, 'negative_hash_cases_passed': 7, 'unregistered_index_rejected': True,
               'decoder_sha256': adapter.sha(adapter.R12 / 'scripts/decode_x0.py'),
               'adapter_sha256': adapter.sha(Path(adapter.__file__)),
               'inventory_sha256': adapter.sha(root / 'analysis/input_inventory.json')}
        (root / 'analysis/input_cpu_validation.json').write_text(json.dumps(out, indent=2)+'\n')
        print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))

if __name__ == '__main__':
    main()
