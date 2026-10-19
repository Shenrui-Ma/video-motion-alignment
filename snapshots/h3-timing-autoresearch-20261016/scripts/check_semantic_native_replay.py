"""Audit the actual native GPU0 replay against GPU2; no model execution.

The five-checkpoint tensor comparison is produced separately on the server.
Missing evidence is an error, not a passing or partial replay gate.
"""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 's05_full_seed1_native_x0'
REPLAY = 's05_semantic_runtime_native_replay_x0'
EVIDENCE = ROOT / 'analysis/semantic_runtime_evidence'
ADMIN = {
    ('5', 'audit_dir'), ('5', 'run_id'),
    ('6', 'audit_dir'), ('6', 'run_id'),
    ('14', 'filename_prefix'),
    ('50', 'audit_dir'), ('50', 'run_id'),
    ('51', 'source_audit_dir'), ('51', 'source_run_id'), ('51', 'run_id'),
    ('52', 'output_dir'), ('52', 'run_id'),
}


def read(path):
    return json.loads(path.read_text())


def normalized(graph):
    graph = copy.deepcopy(graph)
    for node, field in ADMIN:
        # Require the exact field to exist rather than silently ignoring it.
        graph[node]['inputs'][field]
        graph[node]['inputs'][field] = '<administrative>'
    return graph


def decoded_hashes(video, destination):
    subprocess.run([
        '/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2',
        '-i', str(video), '-map', '0:v:0', '-an', '-vsync', '0',
        '-pix_fmt', 'rgb24', '-f', 'framehash', '-hash', 'sha256',
        '-y', str(destination),
    ], check=True)
    rows = []
    for line in destination.read_text().splitlines():
        if line and not line.startswith('#'):
            fields = [x.strip() for x in line.split(',')]
            rows.append({'decoded_bytes': int(fields[-2]), 'sha256': fields[-1]})
    return rows


def main():
    target = ROOT/'analysis/replication/semantic_gpu0_native_replay_gate.json'
    target.unlink(missing_ok=True)  # An interrupted recheck must not leave a stale PASS.
    histories = [read(root/'logs'/f'{name}_history.json')
                 for root, name in [(ROOT, BASE), (EVIDENCE, REPLAY)]]
    configs = [read(ROOT/'configs'/f'{name}.json') for name in (BASE, REPLAY)]
    checks = {
        'both_actual_histories_success': all(
            h['status'].get('completed') and h['status']['status_str'] == 'success'
            for h in histories),
        'actual_executed_graphs_match_saved_configs': all(
            h['prompt'][2] == c for h, c in zip(histories, configs)),
        'all_nonadministrative_graph_fields_equal': normalized(configs[0]) == normalized(configs[1]),
    }
    output_sources = read(EVIDENCE/'audit/native_replay_output_sources.json')
    geometry = []
    for index, run in enumerate((BASE, REPLAY)):
        path = ROOT/'outputs'/f'{run}_00001_.mp4'
        source = output_sources[run]
        record = histories[index]['outputs']['14']['images']
        expected_root = ('/data5/researcher/h3_runs/timing_autoresearch_20261016'
                         + ('_semantic0' if index else ''))
        history_path = (EVIDENCE if index else ROOT)/'logs'/f'{run}_history.json'
        checks[run + '_saved_video_bound_to_actual_history'] = (
            record == [{'filename': path.name, 'subfolder': '', 'type': 'output'}]
            and source['remote'] == expected_root + '/output/' + path.name
            and source['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
            and source['history_sha256'] == hashlib.sha256(history_path.read_bytes()).hexdigest())
        probe = json.loads(subprocess.check_output([
            '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,nb_frames,r_frame_rate,avg_frame_rate,time_base,start_time,duration',
            '-of', 'json', str(path)], text=True))['streams'][0]
        geometry.append(probe)
    checks['same_expected_video_geometry_and_playback_timebase'] = (
        geometry[0] == geometry[1] and geometry[0]['width'] == 1312
        and geometry[0]['height'] == 736 and geometry[0]['nb_frames'] == '141'
        and geometry[0]['r_frame_rate'] == geometry[0]['avg_frame_rate'] == '24/1')
    conditions = [read(root/'audit'/f'{name}_conditioning.json')
                  for root, name in [(ROOT, BASE), (EVIDENCE, REPLAY)]]
    for key in ('prompt', 'input_video', 'native_vae_calls', 'qwen_presentation',
                'tokenization_before_vision_expansion', 'conditioning_embedding',
                'token_tags', 'target_latent_shapes', 'packed_layout'):
        checks['actual_' + key + '_equal'] = conditions[0][key] == conditions[1][key]
    noise = [read(root/'audit'/f'{name}_noise.json')
             for root, name in [(ROOT, BASE), (EVIDENCE, REPLAY)]]
    for key in ('signature', 'actual_noise_streams', 'pair_id'):
        checks['noise_' + key + '_equal'] = noise[0][key] == noise[1][key]
    for root, run in [(ROOT, BASE), (EVIDENCE, REPLAY)]:
        router = read(root/'audit/router'/f'{run}.json')
        checks[run + '_native_1000_calls_zero_routed'] = (
            router['run_id'] == run and router['mode'] == 'native'
            and router['completed_calls'] == 1000 and router['routed_calls'] == 0
            and router['completed_forward_calls'] == 20
            and router['calls_by_forward'] == [50] * 20)
    tensor = read(EVIDENCE/'audit/native_replay_tensor_equality.json')
    manifest_paths = [ROOT/'audit/x0'/BASE/'manifest.json',
                      EVIDENCE/'audit/x0'/REPLAY/'manifest.json']
    manifests = [read(p) for p in manifest_paths]
    checks['tensor_report_bound_to_actual_runs'] = (
        tensor['a'] == '/data5/researcher/h3_runs/timing_autoresearch_20261016/audit/x0/' + BASE
        and tensor['b'] == '/data5/researcher/h3_runs/timing_autoresearch_20261016_semantic0/audit/x0/' + REPLAY
        and tensor['manifest_run_ids'] == [BASE, REPLAY]
        and tensor['manifest_sha256'] == [hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest_paths]
        and all(m['status'] == 'complete' for m in manifests))
    checks['all_five_video_audio_tensors_equal'] = (
        tensor['all_equal'] and len(tensor['rows']) == 5 and {r['stem'] for r in tensor['rows']} ==
        {'x0_step005', 'x0_step010', 'x0_step015', 'x0_step019', 'sampler_final'}
        and all(r['tensors'][k]['equal'] for r in tensor['rows'] for k in ('video', 'audio')))
    for row in tensor['rows']:
        for index, manifest in enumerate(manifests):
            entries = [c for c in manifest['captures'] + [manifest['final_sampler_result']]
                       if c['file'] == row['stem'] + '.pt']
            checks[f"{row['stem']}_manifest_binding_{index}"] = len(entries) == 1 and all(
                row['tensors'][k]['actual_sha256'][index] == entries[0][k]['sha256']
                and row['tensors'][k]['shape'] == entries[0][k]['shape']
                and row['tensors'][k]['dtype'] == entries[0][k]['dtype']
                for k in ('video', 'audio'))
    out = ROOT/'analysis/replication'
    decoded = [decoded_hashes(ROOT/'outputs'/f'{name}_00001_.mp4', out/f'{name}.rgb.sha256')
               for name in (BASE, REPLAY)]
    checks['all_141_decoded_rgb_frames_equal'] = (
        len(decoded[0]) == len(decoded[1]) == 141 and decoded[0] == decoded[1])
    record = {
        'baseline': BASE, 'replay': REPLAY, 'checks': checks,
        'passed': all(checks.values()),
        'decoded_counts': list(map(len, decoded)),
        'matching_decoded_frames': sum(a == b for a, b in zip(*decoded)),
        'video_stream_metadata': geometry,
        'graph_sha256': [hashlib.sha256((ROOT/'configs'/f'{n}.json').read_bytes()).hexdigest()
                         for n in (BASE, REPLAY)],
        'scope': 'Same-input runtime replay only. Not an independent effectiveness sample.',
    }
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(record, ensure_ascii=False))
    raise SystemExit(0 if record['passed'] else 1)


if __name__ == '__main__':
    main()
