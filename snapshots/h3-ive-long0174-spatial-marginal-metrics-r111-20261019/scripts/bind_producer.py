"""Freeze the consumer only after the R111 producer owner freezes its actual CPU package."""
from pathlib import Path
import shutil
import sys
from common import ROOT, read, save, sha, require, bound, verify_graph_control


def bind():
    require(not (ROOT/'CONSUMER_FREEZE.json').exists(), 'preserve the existing consumer freeze')
    projects = ROOT.parent
    producer = projects/'h3-timing-ive-long0174-spatial-marginal-r111-20261019'
    old = projects/'h3-ive-long0174-guidance-metrics-r107-20261019'
    prior = read(old/'configs/contract.json')
    oldcase = prior['cases']['long_0174']
    seal = read(producer/'deploy_manifest.json')
    for rel, record in seal['files'].items():
        require(sha(producer/rel) == record['sha256'], 'producer changed since sealing: '+rel)
    for rel, digest in read(old/'CONSUMER_FREEZE.json')['files'].items():
        require(sha(old/rel) == (digest['sha256'] if isinstance(digest, dict) else digest),
                'R107 consumer changed since sealing')
    incoming = old/'incoming/long_0174'
    for rel, digest in read(incoming/'COLLECTION.json')['files'].items():
        require(sha(incoming/rel) == digest, 'R107 actual intake changed')
    fixed = read(producer/'design/R107_FIXED_BINDING.json')
    require(sha(incoming/'PAIR_RUNTIME_GATE.json') == fixed['gate_sha256'] and
            sha(incoming/'forced.mp4') == fixed['video_sha256'] and
            sha(producer/'design/R107_GRAPH.json') == fixed['graph_sha256'],
            'R107 fixed actual binding differs')
    runtime = read(producer/'configs/runtime.json')
    cfg = {'producer_local': str(producer), 'producer_remote': runtime['remote_root'],
        'fixed_producer_remote': prior['producer_remote'], 'host': 'H3_SERVER_B',
        'run_id': 'r111_long_0174_seed2026101701_forced', 'native_run_id': oldcase['run_id'],
        'producer_seal_sha256': sha(producer/'deploy_manifest.json'),
        'producer_runtime_sha256': sha(producer/'configs/runtime.json'),
        'fixed_binding': fixed,
        'first_six_predictions': oldcase['first_six_predictions'],
        'historical_media': {role: bound(incoming/file) for role, file in
                            [('source', 'source.mp4'), ('native', 'native.mp4'), ('fixed', 'forced.mp4')]},
        'historical_evidence': {'R107_GATE': bound(incoming/'PAIR_RUNTIME_GATE.json'),
            'R107_COLLECTION': bound(incoming/'COLLECTION.json'),
            'R107_GRAPH': bound(incoming/'graph.json'), 'R107_HISTORY': bound(incoming/'history.json'),
            'R96_NATIVE_GATE': oldcase['parent_gate'],
            'R107_FULL145_REVIEW': bound(old/'audit/full_frame_review/REVIEW.json'),
            'R107_REGISTERED_EVENTS': bound(old/'audit/PREREGISTERED_EVENT_REVIEW.json')},
        'geometry': {'total_frames': 158, 'valid_frames': 145, 'fps': 24, 'width': 1312,
                     'height': 736, 'evaluation_crop_xywh': [16, 8, 1280, 720]},
        'method': {'fixed': 'mass_preserve', 'spatial': 'spatial_marginal', 'alpha': 1,
                   'denoising_indices': [6, 15], 'blocks': [0, 50], 'routed_calls': 450},
        'official_MF': {'status': 'WAIT_ACTUAL_R111_OUTPUT', 'scores': None},
        'reference_metric_cache_candidate': str(projects/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r107_long_0174')}
    graph = read(producer/'configs/graphs'/f'{cfg["run_id"]}.json')
    verify_graph_control(graph, read(producer/'design/R107_GRAPH.json'), cfg)
    files = {'producer_deploy_manifest.json': producer/'deploy_manifest.json',
        'producer_runtime.json': producer/'configs/runtime.json',
        'producer_graph.json': producer/'configs/graphs'/f'{cfg["run_id"]}.json',
        'R107_GRAPH.json': producer/'design/R107_GRAPH.json',
        'R107_FIXED_BINDING.json': producer/'design/R107_FIXED_BINDING.json'}
    for name, source in files.items():
        require(not (ROOT/'configs'/name).exists(), 'existing draft contract file; inspect before rebinding')
        shutil.copy2(source, ROOT/'configs'/name)
    save(ROOT/'configs/contract.json', cfg)
    frozen = {str(path.relative_to(ROOT)): sha(path) for folder in ('scripts', 'configs', 'tests')
              for path in sorted((ROOT/folder).rglob('*')) if path.is_file() and '__pycache__' not in path.parts}
    save(ROOT/'CONSUMER_FREEZE.json', {'schema': 'r111-four-column-consumer-freeze-v1',
                                    'files': frozen})
    print({'consumer_freeze_sha256': sha(ROOT/'CONSUMER_FREEZE.json'), 'files': len(frozen),
           'producer_seal_sha256': cfg['producer_seal_sha256'], 'GPU_started': False})


if __name__ == '__main__':
    bind()
