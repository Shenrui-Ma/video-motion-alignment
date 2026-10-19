"""CPU-only exact comparisons of completed, paired x0 captures."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch


def compare(first, second, stems, output):
    torch.set_num_threads(1)
    manifests = []
    for folder in (first, second):
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest.get('status') != 'complete':
            raise ValueError(f'Capture not complete: {folder}')
        manifests.append(manifest)
    rows = []
    for stem in stems:
        paths = [folder / (stem + '.pt') for folder in (first, second)]
        values = [torch.load(p, map_location='cpu', weights_only=True) for p in paths]
        for key in ('geometry', 'step_zero_based', 'total_steps',
                    'snapshot_kind', 'normalization_stage'):
            if values[0]['metadata'][key] != values[1]['metadata'][key]:
                raise ValueError(f'Incompatible metadata: {stem} / {key}')
        tensors = {}
        for key in ('video', 'audio'):
            a, b = [x[key] for x in values]
            if a.shape != b.shape or a.dtype != b.dtype:
                raise ValueError(f'Incompatible tensor: {stem} / {key}')
            hashes = [hashlib.sha256(x.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
                      for x in (a, b)]
            for index, manifest in enumerate(manifests):
                captures = manifest['captures'] + [manifest['final_sampler_result']]
                entries = [x for x in captures if x['file'] == stem + '.pt']
                if len(entries) != 1 or entries[0][key]['sha256'] != hashes[index]:
                    raise ValueError(f'Actual tensor hash differs from capture manifest: {stem}/{key}/{index}')
            tensors[key] = {'equal': torch.equal(a, b) and hashes[0] == hashes[1], 'shape': list(a.shape),
                            'dtype': str(a.dtype),
                            'actual_sha256': hashes,
                            'max_abs': float((a - b).abs().max())}
        rows.append({'stem': stem,
                     'file_sha256': [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
                     'tensors': tensors})
    record = {'a': str(first), 'b': str(second), 'rows': rows,
              'manifest_sha256': [hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest()
                                  for folder in (first, second)],
              'manifest_run_ids': [m['run_id'] for m in manifests],
              'all_equal': all(x['equal'] for r in rows for x in r['tensors'].values()),
              'scope': 'Exact tensor equality on completed captures; per-run IDs intentionally differ'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2))
    return {'output': str(output), 'all_equal': record['all_equal'], 'stems': stems}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('first', type=Path)
    parser.add_argument('second', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--stems', nargs='+', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.first, args.second, args.stems, args.output)))
