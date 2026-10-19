"""Fixed CPU-only transformations of cached source tracks; not generated videos."""
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '0'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PILOT = Path('/Users/researcher/DevProjects/h3-ivebench-pilot-20261017')
OFFICIAL = PILOT/'literature/official_source/metrics/fidelity/motion_fidelity.py'
CACHE = PILOT/'literature/metric_runtime/host41/source_tracking_complete5/tracks/source'
OFFICIAL_SHA = '4be44656ba92ef7f12af58be2db500ec70d3dda93d9d91d81c9681e7ffd3c0ef'
COMMIT = '2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
METHODS = ('interpolate_track', 'compute_frame_by_frame_similarity',
           'synchronize_videos', '_compute_similarity_from_tracks')
IDS = ('short_0210', 'short_0230', 'short_0263', 'short_0352', 'short_0370')
VARIANTS = ('self_full', 'self_common', 'delay_2', 'delay_4', 'delay_8', 'visibility_gap_8')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_json(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def pure_metric():
    import numpy as np
    from scipy.interpolate import interp1d
    from scipy.optimize import linear_sum_assignment
    if sha(OFFICIAL) != OFFICIAL_SHA:
        raise ValueError('official score source SHA mismatch')
    tree = ast.parse(OFFICIAL.read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'MotionFidelityEvaluator')
    methods = [x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name in METHODS]
    if {x.name for x in methods} != set(METHODS):
        raise ValueError('official score methods missing')
    method_hashes = {x.name: hashlib.sha256(ast.dump(x, include_attributes=False).encode()).hexdigest() for x in methods}
    # Nodes are the original AST objects; only class membership and imports are narrowed.
    wrapper = ast.Module(body=[ast.ClassDef(name=cls.name, bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(wrapper)
    namespace = {'np': np, 'interp1d': interp1d, 'linear_sum_assignment': linear_sum_assignment}
    exec(compile(wrapper, str(OFFICIAL), 'exec'), namespace)
    return namespace[cls.name](), method_hashes

def freeze():
    if (HERE/'PROTOCOL.json').exists():
        raise FileExistsError('protocol already frozen')
    if sha(OFFICIAL) != OFFICIAL_SHA:
        raise ValueError('official source differs')
    sources = []
    for pair in IDS:
        report_path = CACHE/pair/'REPORT.json'
        report = json.loads(report_path.read_text())
        path = CACHE/pair/'tracks.npz'
        if not report['passed'] or report['method'] != 'source' or report['pair_id'] != pair:
            raise ValueError('source report role mismatch')
        if report['official_commit'] != COMMIT or sha(path) != report['tracks_sha256']:
            raise ValueError('source binding mismatch')
        n = report['effective_frame_count']
        if report['score_frame_indices'] != list(range(n)) or n < 24:
            raise ValueError('insufficient/irregular source timebase')
        sources.append({'pair_id':pair, 'file':str(path), 'sha256':sha(path),
                        'report':str(report_path), 'report_sha256':sha(report_path), 'N':n})
    protocol = {'schema':'official-mf-synthetic-track-diagnostic-v1',
        'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'frozen_before_scoring':True, 'generated_video_results':False,
        'official_commit':COMMIT, 'official_file':str(OFFICIAL), 'official_sha256':OFFICIAL_SHA,
        'plan_sha256':sha(HERE/'PLAN.md'), 'code_sha256':sha(__file__),
        'source_count':5, 'fixed_variants':list(VARIANTS), 'expected_score_count':30,
        'fps':24, 'common_physical_domain':'integer t in [8,N)',
        'delays_frames':[0,2,4,8], 'target_content_rule':'target at t = source at t-d, visibility from t-d',
        'endpoint_policy':'no wrap, no padding, no extrapolation by transform; fixed common physical support',
        'gap_length_frames':8, 'gap_start_common_index':'floor((N-16)/2)',
        'gap_rule':'target visibility=0 for all points in central 8 frames; coordinates/timestamps unchanged',
        'score_timeout_seconds':180, 'sources':sources}
    write_json(HERE/'PROTOCOL.json', protocol)
    return protocol

def transform(tracks, vis, variant):
    import numpy as np
    n = tracks.shape[1]
    if variant not in VARIANTS or n < 24:
        raise ValueError('unsupported transform or too few frames')
    start = 0 if variant == 'self_full' else 8
    domain = np.arange(start, n, dtype=np.int64)
    delay = int(variant.split('_')[1]) if variant.startswith('delay_') else 0
    target_index = domain-delay
    source = tracks[:, domain, :, :].copy()
    source_vis = vis[:, domain, :].copy()
    target = tracks[:, target_index, :, :].copy()
    target_vis = vis[:, target_index, :].copy()
    gap = None
    if variant == 'visibility_gap_8':
        k = (len(domain)-8)//2
        target_vis[:, k:k+8, :] = 0
        gap = {'common_indices_half_open':[k,k+8],
               'physical_frame_indices_half_open':[int(domain[k]),int(domain[k]+8)]}
    ledger = {'physical_frame_indices':domain.tolist(), 'physical_time_seconds':(domain/24).tolist(),
              'source_original_indices':domain.tolist(), 'target_original_content_indices':target_index.tolist(),
              'target_content_time_seconds':(target_index/24).tolist(),
              'known_delay_frames':delay, 'known_delay_ms':delay/24*1000,
              'gap':gap, 'synthetic_track_diagnostic':True}
    return source, source_vis, target, target_vis, ledger

def load_bound(row):
    import numpy as np
    if sha(row['file']) != row['sha256'] or sha(row['report']) != row['report_sha256']:
        raise ValueError('frozen source binding changed')
    with np.load(row['file'], allow_pickle=False) as data:
        tracks,vis = data['tracks'].copy(),data['visibility'].copy()
    if tracks.shape != (1,row['N'],100,2) or vis.shape != (1,row['N'],100):
        raise ValueError('source shape differs')
    if not np.isfinite(tracks).all() or not np.isfinite(vis).all():
        raise ValueError('source has nonfinite values')
    return tracks,vis

def run():
    import numpy as np
    import scipy
    import torch
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise RuntimeError('CPU-only diagnostic')
    protocol = json.loads((HERE/'PROTOCOL.json').read_text())
    if sha(__file__) != protocol['code_sha256'] or sha(HERE/'PLAN.md') != protocol['plan_sha256']:
        raise ValueError('frozen implementation changed')
    output = HERE/'results'
    output.mkdir(exist_ok=False)
    metric,method_hashes = pure_metric()
    records=[];started=time.monotonic()
    def timeout(_signum,_frame):
        raise TimeoutError('fixed 180 second scoring budget exhausted')
    signal.signal(signal.SIGALRM,timeout)
    signal.alarm(protocol['score_timeout_seconds'])
    try:
        for row in protocol['sources']:
            tracks,vis = load_bound(row)
            for variant in protocol['fixed_variants']:
                s,sv,t,tv,ledger = transform(tracks,vis,variant)
                label = row['pair_id']+'__'+variant
                npz = output/(label+'.npz')
                np.savez_compressed(npz, source_tracks=s, source_visibility=sv,
                    target_tracks=t, target_visibility=tv,
                    physical_frame_indices=np.array(ledger['physical_frame_indices']),
                    source_original_indices=np.array(ledger['source_original_indices']),
                    target_original_content_indices=np.array(ledger['target_original_content_indices']))
                before=time.monotonic()
                value=float(metric._compute_similarity_from_tracks(*[torch.from_numpy(x) for x in (s,sv,t,tv)]))
                if not np.isfinite(value):
                    raise ValueError('nonfinite metric')
                record={'pair_id':row['pair_id'], 'variant':variant, 'motion_fidelity':value,
                    'score_seconds':time.monotonic()-before, 'frame_count':len(ledger['physical_frame_indices']),
                    'source_visible_fraction':float(np.mean(sv>.5)), 'target_visible_fraction':float(np.mean(tv>.5)),
                    'source_valid_points_before_sync':int(np.sum(np.sum(sv[0]>.5,axis=0)>=2)),
                    'target_valid_points_before_sync':int(np.sum(np.sum(tv[0]>.5,axis=0)>=2)),
                    'source_cache_sha256':row['sha256'], 'transformed_npz_sha256':sha(npz), **ledger}
                write_json(output/(label+'.json'),record);records.append(record)
        status='COMPLETE'
    except Exception as error:
        status='FAILED'
        write_json(output/'FAILURE.json',{'type':type(error).__name__,'message':str(error),'completed':len(records)})
        raise
    finally:
        signal.alarm(0)
        status = 'COMPLETE' if len(records)==30 else 'INCOMPLETE'
        summary={'schema':'official-mf-synthetic-track-diagnostic-results-v1','status':status,
            'generated_video_results':False,'new_tracker_calls':0,'new_model_constructions':0,
            'device':'cpu','cuda_initialized':torch.cuda.is_initialized(),'protocol_sha256':sha(HERE/'PROTOCOL.json'),
            'method_ast_sha256':method_hashes,'fixed_source_count':5,'expected_score_count':30,
            'actual_score_count':len(records),'wall_seconds':time.monotonic()-started,
            'runtime':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'torch':torch.__version__},
            'per_case':[{'pair_id':x['pair_id'],'variant':x['variant'],'MF':x['motion_fidelity'],
                         'known_delay_frames':x['known_delay_frames'],'known_delay_ms':x['known_delay_ms'],
                         'frame_count':x['frame_count'],'source_visible_fraction':x['source_visible_fraction'],
                         'target_visible_fraction':x['target_visible_fraction']} for x in records],
            'means_by_variant':{v:float(np.mean([x['motion_fidelity'] for x in records if x['variant']==v]))
                                for v in VARIANTS if sum(x['variant']==v for x in records)==5}}
        write_json(HERE/'SUMMARY.json',summary)
    return summary

if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze']:
        print(json.dumps(freeze(),indent=2))
    elif sys.argv[1:] == ['--run']:
        print(json.dumps(run(),indent=2))
    else:
        raise SystemExit('use --freeze or --run')
