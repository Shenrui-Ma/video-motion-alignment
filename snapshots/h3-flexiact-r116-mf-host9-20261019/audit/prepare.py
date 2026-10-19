"""Bind actual R116 pair and reuse byte-identical official source tracks; CPU only."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, sys, time

R = Path(__file__).resolve().parents[1]
B = R.parent
C = B/'h3-flexiact-h2a1-game4-repair-metrics-r116-20261019'
OLD = B/'h3-flexiact-repair-mf-r104-r105-20261019/pairs/r104/human2animal_1__movie_man_11'
CASE = 'human2animal_1__game_man_4'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())

def save(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2)+'\n')

def cp(p, q):
    q.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, q)

def bound(p):
    return {'file': str(p), 'sha256': sha(p)}

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

def main(inventory_id):
    assert not (R/'SEAL.json').exists()
    inp = C/'prepared'/CASE/'paired/MF_INPUTS.json'
    m = read(inp)
    subprocess.run([sys.executable, '-c',
        'import sys;sys.path.insert(0,'+repr(str(C/'scripts'))+');'
        'from common import validate_static;from paired import verify_pair_intake;'
        'validate_static();verify_pair_intake('+repr(CASE)+')'], check=True)
    assert m['evaluate_indices'] == list(range(0, 147, 3)) and m['evaluation_fps'] == 8
    assert m['valid_frames'] == 147 and m['total_frames'] == 158
    for name in ('gate', 'collection', 'provenance'):
        assert sha(m[name]['file']) == m[name]['sha256']
        cp(m[name]['file'], R/'configs'/(name.upper()+'.json'))
    cp(inp, R/'configs/CONSUMER_INPUTS.json')
    gate = read(m['gate']['file'])
    assert gate['passed'] and all(v is True for v in gate['checks'].values())
    case = R/'cases'/CASE
    for arm in ('source', 'native', 'forced'):
        assert sha(m['raw_videos'][arm]['file']) == m['raw_videos'][arm]['sha256']
    cp(m['raw_videos']['source']['file'], case/'source_full.mp4')
    source = m['official_reference']
    assert sha(source['file']) == source['sha256']
    cp(source['file'], case/'source_score.mp4')
    for name in ('REPORT.json', 'tracks.pt'):
        cp(OLD/'actual_host9/tracks/reference'/name, case/'tracks/source'/name)
    old_report = read(case/'tracks/source/REPORT.json')
    assert old_report['case']['sha256'] == source['sha256']
    assert sha(case/'tracks/source/tracks.pt') == old_report['tracks_sha256']
    original_result = read(OLD/'RESULT_VERIFIED.json')
    release = original_result['release']
    assert sha(release['file']) == release['sha256']
    cp(release['file'], R/'configs/CACHED_SOURCE_RELEASE.json')
    release_helper = B/'h3-flexiact-character-repair-mf-r98-20261019/runtime/release/release49.py'
    assert sha(release_helper) == '5bd956e4225d23e97429c4a09d8302477b6d392b176392e13ce0faf8b41fef3f'
    sample = module('release49', release_helper)
    pixels = module('pixels', R/'runtime/ive/metric_runtime/ive_mf_adapter.py')
    hashes = lambda p: pixels.frame_hashes(p, '/opt/homebrew/bin/ffmpeg')
    targets = []
    for arm in ('native', 'forced'):
        assert gate['runs'][arm]['video']['sha256'] == m['raw_videos'][arm]['sha256']
        full = case/arm/'full.mp4'
        cp(m['raw_videos'][arm]['file'], full)
        score = case/arm/'score.mp4'
        sample.run(full, score)
        mapping = read(score.with_suffix('.mapping.json'))
        assert mapping['decoded_frame_md5_equal'] and mapping['terminal_padding_excluded']
        targets.append({'role': arm, 'full_file': arm+'/full.mp4', 'full_sha256': sha(full),
            'score_file': arm+'/score.mp4', 'score_sha256': sha(score), 'score_frame_md5': hashes(score),
            'inventory_bindings': [{'id': inventory_id, 'field': 'native' if arm == 'native' else 'guided'}]})
    value = {'schema': 'r116-flex-official-mf-v1', 'benchmark': 'FlexiAct',
        'canonical_id': 'human/human2animal_1/000', 'valid_frames': 147,
        'evaluation_frames': 49, 'evaluation_fps': 8, 'source_full_sha256': sha(case/'source_full.mp4'),
        'source_score_sha256': sha(case/'source_score.mp4'), 'source_frame_md5': hashes(case/'source_score.mp4'),
        'source_cache': {'report_sha256': sha(case/'tracks/source/REPORT.json'),
                         'tracks_sha256': sha(case/'tracks/source/tracks.pt')},
        'actual_pair_gate_sha256': m['gate']['sha256'], 'consumer_inputs_sha256': sha(inp),
        'targets': targets}
    save(case/'INPUTS.json', value)
    save(R/'configs/PLAN.json', {'groups': [CASE], 'jobs': [{'case': CASE, 'role': arm} for arm in ('native','forced')]})
    runtime = read(B/'h3-ive-r115-mf-host9-20261019/configs/RUNTIME.json')
    runtime.update(gpu_uuid='GPU-REDACTED',
        remote_root='/home/researcher/h3_runs/flexiact_r116_mf_host9_20261019',
        checkpoint='/data5/researcher/h3_runs/flexiact_official_metric_20261017/weights/cotracker_stride_4_wind_8.pth',
        checkpoint_sha256='dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3',
        peer_roots=['/home/researcher/h3_runs/timing_ive_basketball_framing_repair_r117_20261019'])
    save(R/'configs/RUNTIME.json', runtime)
    sys.path.insert(0, str(R/'scripts'))
    from common import validate_flex_report
    validate_flex_report(old_report, value, 'source')
    assert 'torch' not in sys.modules
    save(R/'audit/SOURCE_CACHE_VERIFIED.json', {'passed': True, 'source_media': bound(case/'source_score.mp4'),
        'source_report': bound(case/'tracks/source/REPORT.json'), 'source_tracks': bound(case/'tracks/source/tracks.pt'),
        'previous_score_and_release': bound(OLD/'RESULT_VERIFIED.json'), 'checkpoint_sha256': runtime['checkpoint_sha256'],
        'grid_size': 55, 'mask': None, 'frames': 49, 'fps': 8, 'original_indices': list(range(49)),
        'scientific_numeric_source': str(B/'h3-display-pending-mf-20261019/runtime/flex'),
        'scope': 'same source bytes, physical instants, checkpoint, author tracker and settings; cached actual source reused'})
    save(R/'audit/PREPARED.json', {'passed': True, 'actual_pair': True, 'GPU_started': False,
        'consumer_inputs_sha256': sha(inp), 'targets': len(targets), 'source_cache_reused': True,
        'ready_to_seal_after_actual_producer_release': True, 'unix': time.time()})

if __name__ == '__main__':
    main(sys.argv[1])
