"""Frozen CPU-only diagnostic; never imports Comfy, a model, VAE, or video code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch
import torch.nn.functional as F

PARAMS = dict(grid=4, radius_bins=6, transition_penalty=.05,
              ambiguity_margin=.02, cycle_tolerance_bins=1,
              minimum_feature_norm=1e-10, scale_floor_fraction=.1,
              shifts=[-2, -1, 0, 1, 2], fps=24)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def signature(z):
    z = z.detach().contiguous().cpu()
    return dict(shape=list(z.shape), dtype=str(z.dtype),
                sha256=hashlib.sha256(z.view(torch.uint8).numpy().tobytes()).hexdigest())


def timeline(n, valid_frames):
    spans = torch.tensor([(1, 4, 4, 4, 4)[i % 5] for i in range(n)])
    starts = torch.cat((torch.zeros(1, dtype=torch.int64), spans.cumsum(0)[:-1]))
    ends = starts + spans - 1
    return starts, ends, (starts + (spans - 1) / 2).double(), ends < valid_frames


def pool(z):
    assert z.ndim == 5 and z.shape[0] == 1 and z.device.type == 'cpu'
    return F.adaptive_avg_pool2d(z[0].permute(1, 0, 2, 3).double(), (4, 4))


def features(p, ids, centers, scale=None):
    if len(ids) < 3:
        raise ValueError('too few full valid bins')
    values = (p[2:] - p[:-2]) / ((centers[ids[2:]] - centers[ids[:-2]]) / 24)[:, None, None, None]
    if scale is None:
        scale = values.square().mean(dim=(0, 2, 3)).sqrt()
        positive = scale[scale > 1e-10]
        floor = max(1e-8, float(positive.median()) * .1 if len(positive) else 1e-8)
        scale = scale.clamp_min(floor)
    vectors = (values / scale[None, :, None, None]).flatten(1)
    norms = vectors.norm(dim=1)
    normalized = vectors / norms.clamp_min(1e-30)[:, None]
    return normalized, ids[1:-1], norms > 1e-10, scale


def path_match(cost, src_ids, target_ids):
    """O(T^2) DP with independent backtrace; no in-place changes to inputs."""
    nt, ns = cost.shape
    dp = [[float('inf')] * ns for _ in range(nt)]
    back = [[None] * ns for _ in range(nt)]
    for i in range(nt):
        for j in range(ns):
            if abs(int(target_ids[i]) - int(src_ids[j])) > 6:
                continue
            cij = float(cost[i, j])
            if i == 0:
                dp[i][j] = cij
                continue
            choices = [(dp[i-1][j-d] + .05 * abs(d-1), j-d)
                       for d in (0, 1, 2) if j >= d]
            v, k = min(choices)
            dp[i][j] = v + cij
            back[i][j] = k
    j = min(range(ns), key=lambda k: dp[-1][k])
    if not torch.isfinite(torch.tensor(dp[-1][j])):
        raise ValueError('no valid monotone alignment')
    trace = [j]
    for i in range(nt-1, 0, -1):
        j = back[i][j]
        trace.append(j)
    return list(reversed(trace))


def summarize(xs):
    return dict(n=len(xs), mean=sum(xs)/len(xs), median=statistics.median(xs),
                mean_abs=sum(abs(x) for x in xs)/len(xs)) if xs else dict(n=0, mean=None, median=None, mean_abs=None)


def align(src, target, src_ids, target_ids, centers, sv, tv):
    cost = (1 - target @ src.T).clamp(0, 2)
    path = path_match(cost, src_ids, target_ids)
    reverse = path_match(cost.T, target_ids, src_ids)
    rows = []
    for i, j in enumerate(path):
        legal = [k for k in range(len(src_ids)) if abs(int(target_ids[i])-int(src_ids[k])) <= 6]
        other = [k for k in legal if abs(int(src_ids[k])-int(src_ids[j])) >= 2]
        margin = min((float(cost[i, k]-cost[i, j]) for k in other), default=None)
        cycle = abs(int(target_ids[reverse[j]]) - int(target_ids[i]))
        reasons = []
        if not (bool(sv[j]) and bool(tv[i])): reasons.append('no_temporal_information')
        if margin is None or margin < .02: reasons.append('ambiguous_local_match')
        if float(cost[i, j]) >= 1: reasons.append('nonpositive_cosine')
        if cycle > 1: reasons.append('cycle_inconsistent')
        rows.append(dict(target_bin=int(target_ids[i]), source_bin=int(src_ids[j]),
                         offset_frames=float(centers[target_ids[i]]-centers[src_ids[j]]),
                         cost=float(cost[i,j]), margin=margin, cycle_error_bins=cycle,
                         accepted=not reasons, reasons=reasons))
    return dict(rows=rows, all_summary=summarize([r['offset_frames'] for r in rows]),
                accepted_summary=summarize([r['offset_frames'] for r in rows if r['accepted']]),
                accepted_fraction=sum(r['accepted'] for r in rows)/len(rows),
                cost_matrix=cost.tolist(), source_bins=src_ids.tolist(), target_bins=target_ids.tolist())


def calibrate(p, ids, centers):
    f, fi, fv, scale = features(p, ids, centers)
    shift_rows = []
    for delta in [-2, -1, 0, 1, 2]:
        # Logical target ids stay on original timeline; values come from id-delta.
        keep = [(i, int(t)-delta) for i,t in enumerate(ids) if int(ids[0]) <= int(t)-delta <= int(ids[-1])]
        ti = torch.tensor([int(ids[i]) for i,_ in keep])
        qp = torch.stack([p[s-int(ids[0])] for _,s in keep])
        q, qi, qv, _ = features(qp, ti, centers, scale)
        result = align(f, q, fi, qi, centers, fv, qv)
        for r in result['rows']:
            expected = r['target_bin']-delta
            r['expected_source_bin'] = expected
            r['absolute_bin_error'] = abs(r['source_bin']-expected)
            r['expected_offset_frames'] = float(centers[r['target_bin']]-centers[expected])
            r['physical_error_frames'] = abs(r['offset_frames']-r['expected_offset_frames'])
        informative = [r for i,r in enumerate(result['rows']) if bool(qv[i])]
        fraction = sum(r['absolute_bin_error'] <= .5 for r in informative)/len(informative) if informative else None
        accepted = [r for r in result['rows'] if r['accepted']]
        sign = all(r['offset_frames']*delta > 0 for r in accepted) if delta and accepted else (True if delta == 0 else None)
        result.update(delta_bins=delta, correct_fraction=fraction,
                      sign_correct_on_accepted=sign,
                      passed=bool(fraction is not None and fraction >= .9 and (delta == 0 or sign is True)))
        shift_rows.append(result)
    bias = torch.linspace(-5, 5, p.shape[1], dtype=torch.float64)[None,:,None,None]
    g, gi, gv, _ = features(p+bias, ids, centers, scale)
    before = align(f, f, fi, fi, centers, fv, fv)
    after = align(f, g, fi, gi, centers, fv, gv)
    maxdiff = float((g-f).abs().max())
    same = [r['source_bin'] for r in before['rows']] == [r['source_bin'] for r in after['rows']]
    return dict(shifts=shift_rows, all_shifts_passed=all(r['passed'] for r in shift_rows),
                static_bias=dict(max_descriptor_difference=maxdiff, same_path=same, passed=maxdiff <= 1e-8 and same))


def load_input(path, expected_shape, expected_sig=None, expected_file=None, is_snapshot=False):
    start = time.perf_counter()
    digest = sha(path)
    if expected_file and digest != expected_file: raise ValueError('file SHA mismatch: '+path)
    data = torch.load(path, map_location='cpu', weights_only=True)
    z = data['video'] if is_snapshot else data
    sig = signature(z)
    if sig['shape'] != expected_shape or sig['dtype'] != 'torch.float32': raise ValueError('shape/dtype mismatch')
    if expected_sig and sig['sha256'] != expected_sig: raise ValueError('tensor SHA mismatch')
    if not bool(torch.isfinite(z).all()): raise ValueError('nonfinite input')
    return z, dict(file=path, file_sha256=digest, bytes=Path(path).stat().st_size,
                   tensor_signature=sig, read_seconds=time.perf_counter()-start,
                   metadata=data['metadata'] if is_snapshot else None)


def run_row(row):
    start = time.perf_counter()
    manifest_path = Path(row['capture_dir'])/'manifest.json'
    if sha(manifest_path) != row['manifest_sha256']: raise ValueError('capture manifest changed')
    m = json.loads(manifest_path.read_text())
    if m['status'] != 'complete' or m['seed'] != 2026101701 or m['normalization_stage'] != 'after_process_latent_out':
        raise ValueError('capture contract mismatch')
    src, source_evidence = load_input(row['source_file'], row['shape'], row['source_tensor_sha256'], row['source_file_sha256'])
    starts, ends, centers, valid = timeline(src.shape[2], row['valid_frames'])
    ids = torch.nonzero(valid).flatten()
    psrc = pool(src)[ids]
    del src
    result = dict(case=row['case'], method=row['method'], host_key=row['host_key'],
                  source=source_evidence, capture_manifest_sha256=sha(manifest_path),
                  seed=m['seed'], prompt_sha256=row['prompt_sha256'],
                  timeline=dict(starts=starts.tolist(), ends=ends.tolist(), centers_frames=centers.tolist(),
                                complete_valid_bins=ids.tolist(), valid_frames=row['valid_frames']),
                  source_calibration=calibrate(psrc,ids,centers), snapshots=[])
    prepared=[]
    # All self controls run before any source -> edited score is computed.
    for name in ['x0_step009.pt', 'sampler_final.pt']:
        rec = next(r for r in m['captures']+[m['final_sampler_result']] if r['file']==name)
        z, ev = load_input(str(manifest_path.parent/name), row['shape'], rec['video']['sha256'], is_snapshot=True)
        if ev['metadata']['run_id'] != m['run_id'] or ev['metadata']['snapshot_kind'] != rec['snapshot_kind']:
            raise ValueError('snapshot identity mismatch')
        p = pool(z)[ids];del z
        prepared.append((name,p,ev,calibrate(p,ids,centers)))
    f,fi,fv,scale=features(psrc,ids,centers)
    for name,p,ev,cal in prepared:
        g,gi,gv,_=features(p,ids,centers,scale)
        cross=align(f,g,fi,gi,centers,fv,gv)
        event_rows=[]
        for event in row['events']:
            lo,hi=event['source_interval']
            matching=[r for r in cross['rows'] if int(ends[r['source_bin']])>=lo and int(starts[r['source_bin']])<=hi]
            event_rows.append(dict(**event,all=summarize([r['offset_frames'] for r in matching]),
                                   accepted=summarize([r['offset_frames'] for r in matching if r['accepted']]),
                                   matched_rows=matching))
        cross['events']=event_rows
        result['snapshots'].append(dict(name=name,input=ev,self_calibration=cal,cross_identity=cross))
    result['wall_seconds']=time.perf_counter()-start
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--host-key',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    if torch.cuda.is_initialized():raise RuntimeError('CUDA must never initialize')
    inp=json.loads(Path(args.inputs).read_text());out=dict(schema='h3-latent-phase-calibration-v1',params=PARAMS,
        script_sha256=sha(__file__),inputs_sha256=sha(args.inputs),prereg_sha256=inp['prereg_sha256'],
        torch_version=torch.__version__,device='cpu',n_threads=torch.get_num_threads(),rows=[],errors=[])
    started=time.perf_counter()
    for row in inp['rows']:
        if row['host_key']!=args.host_key:continue
        try:out['rows'].append(run_row(row))
        except Exception as e:out['errors'].append(dict(case=row['case'],method=row['method'],error=repr(e)))
    out['wall_seconds']=time.perf_counter()-started
    out['cuda_initialized']=torch.cuda.is_initialized()
    Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(out=args.out,rows=len(out['rows']),errors=out['errors'],wall_seconds=out['wall_seconds'])))
    return 1 if out['errors'] else 0


if __name__=='__main__':raise SystemExit(main())
