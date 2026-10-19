"""Apply two frozen VAE-phase diagnostics to existing cross-identity snapshots."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = 'f3434d45a1784e9ec20752131d4049757a0c66a5257539cf29bcc9411a2b64ac'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_tensor(item, snapshot, torch):
    path = Path(item['path'])
    if sha(path) != item['file_sha256']:
        raise ValueError('Input file changed: ' + str(path))
    data = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    z = data['video'] if snapshot else data
    actual = dict(shape=list(z.shape), dtype=str(z.dtype),
                  sha256=hashlib.sha256(z.contiguous().view(torch.uint8).numpy()).hexdigest())
    if actual != item['tensor'] or tuple(z.shape) != (1,24,42,46,82):
        raise ValueError('Tensor content/shape/dtype mismatch')
    if snapshot:
        if data['metadata'] != item['metadata']:
            raise ValueError('Snapshot metadata changed')
        if data['metadata']['normalization_stage'] != 'after_process_latent_out':
            raise ValueError('Wrong latent normalization')
    if not bool(torch.isfinite(z).all()):
        raise ValueError('Nonfinite input')
    return z


def region_array(z, roi):
    y0,y1,x0,x1 = roi
    return z[0,:,:,y0:y1,x0:x1].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64)


def main():
    started = time.time()
    if sha(HERE / 'PROTOCOL.json') != PROTOCOL_SHA:
        raise RuntimeError('Frozen protocol changed')
    p = json.loads((HERE / 'PROTOCOL.json').read_text())
    if sha(p['method_source']) != p['method_source_sha256']:
        raise RuntimeError('Frozen method changed')
    spec = importlib.util.spec_from_file_location('frozen_phase_method', p['method_source'])
    method = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(method)
    import torch
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise RuntimeError('CUDA must stay uninitialized')
    result = dict(schema='h3-cross-identity-phase-readout-v1', protocol_sha256=PROTOCOL_SHA,
                  script_sha256=sha(__file__), CPU_only=True, sources={}, torch=torch.__version__, numpy=np.__version__,
                  pose_labels_read=False, primary_RGB_endpoint_unchanged=True)
    checked = []
    for source, info in p['sources'].items():
        ref = load_tensor(info['reference'], False, torch)
        checked.append(info['reference'])
        signals = {}
        for label, roi in info['regions'].items():
            array = region_array(ref, roi)
            signals[label] = {m: method.signal(array, m) for m in p['methods']}
        source_result = dict(windows_inclusive=info['windows_inclusive'], regions=info['regions'], runs={})
        for name, item in info['runs'].items():
            z = load_tensor(item, True, torch)
            checked.append(item)
            run = dict(input_path=item['path'], file_sha256=item['file_sha256'], tensor=item['tensor'],
                       snapshot_metadata=item['metadata'], regions={})
            for label, roi in info['regions'].items():
                array = region_array(z, roi)
                run['regions'][label] = {}
                for name_method in p['methods']:
                    a = signals[label][name_method]
                    b = method.signal(array, name_method)
                    rows = [method.scan(a,b,w,p['reject_rules']) for w in info['windows_inclusive']]
                    run['regions'][label][name_method] = dict(
                        source_signal_rms=float(np.sqrt(np.mean(a[1]*a[1]))),
                        target_signal_rms=float(np.sqrt(np.mean(b[1]*b[1]))), rows=rows)
                    print(source,name,label,name_method,
                          [(r['best']['lag_frames'] if r['best'] else None,r['accepted'],r['rejection_reasons']) for r in rows], flush=True)
            source_result['runs'][name] = run
        result['sources'][source] = source_result
    for item in checked:
        if sha(item['path']) != item['file_sha256']:
            raise RuntimeError('Input changed during CPU analysis')
    result['elapsed_seconds'] = time.time()-started
    result['CUDA_initialized'] = torch.cuda.is_initialized()
    with (HERE / 'RESULTS.json').open('x') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n')
    print('Complete. seconds=',result['elapsed_seconds'],'CUDA=',result['CUDA_initialized'],flush=True)


if __name__ == '__main__':
    main()
