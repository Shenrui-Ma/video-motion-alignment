"""Read-only, per-video prompt provenance audit; does not mutate inventory."""
from pathlib import Path
import hashlib
import json
import time

BASE = Path('/Users/researcher/DevProjects')
ROOT = BASE / 'h3-benchmark-all-results-showcase-20261018'
OUT = Path(__file__).parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

inventory_path = ROOT / 'inventory/ivebench.json'
inventory = read(inventory_path)
rows = {x['id']: x for x in inventory['items']}
bindings = {}

def actual(row_id, column, relative, prefix, gate_name='PAIR_RUNTIME_GATE.json', run_key=None,
           history_name=None, graph_name=None, job_name=None):
    row = rows[row_id]
    directory = BASE / relative
    history_path = directory / (history_name or f'{prefix}_history.json')
    graph_path = directory / (graph_name or f'{prefix}_graph.json')
    job_path = directory / (job_name or f'{prefix}_job.json')
    gate_path = directory / gate_name
    history, job, gate = read(history_path), read(job_path), read(gate_path)
    graph = history['prompt'][2]
    assert history['status']['completed'] and history['status']['status_str'] == 'success'
    assert history['prompt'][1] == job['prompt_id']
    assert job['status'] == 'success'
    checks = ['history_completed_success', 'history_prompt_id_equals_job']
    if graph_path.exists():
        assert read(graph_path) == graph
        assert job['graph_sha256'] == sha(graph_path)
        checks += ['graph_equals_actual_history_graph', 'graph_bytes_equal_actual_job_hash']
    else:
        graph_path = None
    gate_run = gate['runs'][run_key or prefix] if 'runs' in gate else gate
    assert gate['passed'] is True
    assert gate_run['run_id'] == job['name']
    field = f'{column}_video_path'
    video_path = Path(row[field])
    video_sha = sha(video_path)
    assert video_sha == gate_run['video']['sha256']
    if row.get('media_sha256', {}).get(field):
        assert video_sha == row['media_sha256'][field]
    output_names = [v['filename'] for node in history['outputs'].values()
                    for v in node.get('images', []) if v.get('type') == 'output']
    assert Path(gate_run['video']['file']).name in output_names
    checks += ['gate_passed', 'gate_run_equals_job', 'actual_video_equals_gate_sha',
               'history_output_filename_equals_gate_output']
    for name, path in [('history_sha256', history_path), ('job_sha256', job_path)]:
        if name in gate_run:
            assert gate_run[name] == sha(path)
            checks.append(name + '_equals_gate')
    prompt_nodes = [(k, node['inputs']['prompt']) for k, node in graph.items()
                    if isinstance(node.get('inputs', {}).get('prompt'), str)]
    assert len(prompt_nodes) == 1, prompt_nodes
    node_id, text = prompt_nodes[0]
    official = row.get('original_task', {}).get('edit_prompt', row.get('task'))
    protocol = 'official_edit_prompt' if text == official else (
        'structured_adaptation' if text.startswith('subject_definitions:') else 'adapted_prompt')
    evidence = [history_path, job_path, gate_path] + ([graph_path] if graph_path else [])
    value = {
        'text': text, 'prompt_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'protocol': protocol, 'exact_official_edit_prompt': text == official,
        'graph_bindings': [{'graph': str(graph_path or history_path),
                            'graph_sha256': sha(graph_path or history_path),
                            'node_id': node_id,
                            'field': 'inputs.prompt' if graph_path else 'prompt[2].inputs.prompt'}],
        'actual_history': str(history_path), 'actual_history_sha256': sha(history_path),
        'prompt_id': job['prompt_id'], 'run_id': job['name'],
        'media': str(video_path), 'media_sha256': video_sha,
        'checks': checks, 'evidence_sha256': {str(p): sha(p) for p in evidence},
        'scope': f'Actual {column} video column, bound by output and media SHA.'
    }
    bindings.setdefault(row_id, {})[column] = value
    return value

for rid, directory in [
    ('r71_short_0210', 'h3-timing-ivebench-prompt-pair-r71-20261018/audit/consumer/incoming'),
    ('r78_short_0370', 'h3-timing-local-edit-protocol-r78-20261018/audit/consumer/incoming')]:
    for prefix, column in [('p0', 'ordinary'), ('p1', 'alternative')]:
        actual(rid, column, directory, prefix, history_name=f'{prefix}_logs_history.json',
               graph_name=f'{prefix}_graphs.json', job_name=f'{prefix}_logs_job.json')

actual('r97_short_0358_extended', 'guided',
       'h3-ive-glasses-schedule-metrics-r97-20261019/incoming', 'extended',
       gate_name='CONTROL_RUNTIME_GATE.json')
for prefix, column in [('native', 'ordinary'), ('forced', 'alternative')]:
    actual('r97_short_0358_extended', column,
           'h3-ive-subject-capacity-metrics-r89-20261018/incoming/short_0358', prefix)

for sid in ['short_0210', 'short_0230', 'short_0352']:
    actual(f'r99_{sid}', 'guided', f'h3-ive-p1-guidance-metrics-r99-20261019/incoming/{sid}',
           'forced', history_name='history.json', graph_name='graph.json', job_name='job.json')

for rid, directory in [
    ('r107_long_0174', 'h3-ive-long0174-guidance-metrics-r107-20261019/incoming/long_0174'),
    ('r111_long_0174_spatial', 'h3-ive-long0174-spatial-marginal-metrics-r111-20261019/incoming/long_0174')]:
    actual(rid, 'guided', directory, 'forced', history_name='history.json', graph_name='graph.json', job_name='job.json')

for prefix, column in [('euler', 'ordinary'), ('res_multistep', 'alternative')]:
    actual('r106_short_0252_sampler_control', column,
           'h3-sampler-control-metrics-r106-20261019/incoming', prefix, gate_name='gate.json')

for prefix in ['fixed_one_bin', 'matched_one_bin']:
    actual(f'r115_long_0174_{prefix}', 'guided',
           'h3-ive-long0174-correspondence-metrics-r115-20261019/incoming/long_0174', prefix)

actual('r107_long_0174', 'ordinary',
       'h3-ive-native-screen-metrics-r96-20261018/incoming/long_0174', 'native',
       gate_name='NATIVE_RUNTIME_GATE.json')

# Reuse a prompt only when the output bytes are exactly the same already-bound video.
video_index = {}
for rid, row in rows.items():
    merged = dict(row.get('actual_prompt_by_column', {}))
    merged.update(bindings.get(rid, {}))
    for column, value in merged.items():
        field = f'{column}_video_path'
        if not row.get(field):
            continue
        p = Path(row[field])
        digest = sha(p)
        if row.get('media_sha256', {}).get(field):
            assert digest == row['media_sha256'][field]
        for e in value.get('graph_bindings', []):
            assert sha(e['graph']) == e['graph_sha256']
        video_index.setdefault(digest, []).append((rid, column, value))

missing = []
for rid in list(bindings):
    row = rows[rid]
    for column in ['ordinary', 'guided', 'alternative', 'fixed_control']:
        field = f'{column}_video_path'
        if not row.get(field) or column in bindings[rid]:
            continue
        p = Path(row[field])
        digest = sha(p)
        candidates = video_index.get(digest, [])
        if not candidates:
            missing.append({'row_id': rid, 'column': column, 'media_sha256': digest})
            continue
        texts = {value['text'] for _, _, value in candidates}
        assert len(texts) == 1, (rid, column)
        source_id, source_column, value = candidates[0]
        copied = dict(value)
        copied.update({'media': str(p), 'media_sha256': digest,
                       'same_video_reuse': {'row_id': source_id, 'column': source_column,
                                            'inventory_sha256': sha(inventory_path)},
                       'scope': f'Exact same output bytes as {source_id}/{source_column}; prompt reused for {column}.'})
        bindings[rid][column] = copied

result = {'schema': 'h3.prompt-column-evidence.v1', 'created_unix': time.time(),
          'inventory_sha256': sha(inventory_path), 'row_count': len(bindings),
          'column_count': sum(map(len, bindings.values())),
          'status': 'CANDIDATE_EVIDENCE_ONLY_INVENTORY_UNCHANGED',
          'rows': bindings, 'unresolved': missing}
path = OUT / 'CANDIDATES_VERIFIED.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(path), 'sha256': sha(path), 'rows': len(bindings),
                  'columns': result['column_count'], 'unresolved': missing}, ensure_ascii=False))
