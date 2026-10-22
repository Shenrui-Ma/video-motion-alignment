"""Freeze two previously selected research cases; never submit or mutate a queue."""
import copy
import hashlib
import json
from pathlib import Path

B = Path(__file__).resolve().parent
E = B.parents[2]
OUT = B / 'field_extension_two'
SOURCE = E / 'innovation/pilot_ten/other_packages/temporal_coverage_v2/host41/remaining_eight'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (OUT / 'PUBLISHED.json').exists():
        raise RuntimeError('Published extension is immutable')
    package = E / 'innovation/feature_gain_field'
    ready = json.loads((package / 'READY.json').read_text())
    assert ready['test_exit_code'] == 0
    for name, expected in ready['source_shas'].items():
        assert digest(package / name) == expected, name
    pilot = json.loads((B / 'field_pilots/jobs.json').read_text())['jobs'][0]
    pilot_graph = json.loads((B / 'field_pilots' / pilot['graph']).read_text())
    originals = json.loads((SOURCE / 'jobs.json').read_text())['jobs']
    selected = ['long_0039', 'long_0059']
    jobs, checks = [], []
    (OUT / 'graphs').mkdir(parents=True, exist_ok=True)
    for task in selected:
        matches = [j for j in originals if j['metadata']['task_id'] == task]
        assert len(matches) == 1
        source = matches[0]
        job = copy.deepcopy(source)
        old = json.loads((SOURCE / source['graph']).read_text())
        graph = copy.deepcopy(old)
        jid = f'adapt41_{task}_temporal_gain_field'
        job.update(id=jid, graph=f'graphs/{jid}.json', expected_output_prefix=jid+'/', max_attempts=1)
        graph['14']['inputs']['filename_prefix'] = jid + '/{attempt_id}'
        graph['50'] = copy.deepcopy(pilot_graph['50'])
        for key in ('model', 'positive', 'start_frame', 'end_frame', 'block_start', 'block_end', 'step_start', 'step_end'):
            graph['50']['inputs'][key] = copy.deepcopy(old['50']['inputs'][key])
        assert graph['50']['inputs']['end_frame'] == source['metadata']['valid_frames'] - 1
        assert graph['50']['inputs']['step_start'] == 0 and graph['50']['inputs']['step_end'] == 20
        m = job['metadata']
        for key in ('coverage_unit', 'routing_constraints', 'solver', 'fallback_policy', 'solver_change'):
            m.pop(key, None)
        for key in ('method', 'cohort', 'attention_formula', 'strength_scope', 'calibration', 'alpha_scope', 'temporal_regularization', 'no_evidence_rule'):
            m[key] = copy.deepcopy(pilot['metadata'][key])
        m.update(innovation_parameters=copy.deepcopy(graph['50']['inputs']),
                 innovation_status='independent_gain_field_extension_pending_runtime_check',
                 reference_source_job=source['id'],
                 comparison_scope='same historical prompt/seed/cache/model/geometry; reused native/global_weak',
                 selection_basis='Two remaining original user-selected core cases; fixed before extension results; no per-case tuning')
        raw = (json.dumps(graph, ensure_ascii=False, indent=2)+'\n').encode()
        m['graph_sha256'] = hashlib.sha256(raw).hexdigest()
        (OUT / job['graph']).write_bytes(raw)
        changed = [k for k in old if old[k] != graph[k]]
        assert set(changed) == {'14', '50'}
        for key in ('prompt', 'seed', 'geometry', 'valid_frames', 'fps', 'comparison_outputs', 'source_video'):
            assert m[key] == source['metadata'][key], key
        jobs.append(job)
        checks.append(dict(task=task, source_job=source['id'], source_graph_sha256=digest(SOURCE/source['graph']),
                           changed_nodes=sorted(changed), graph_sha256=m['graph_sha256'],
                           prompt_seed_cache_model_geometry_equal=True, geometry=m['geometry']))
    (OUT / 'jobs.json').write_text(json.dumps({'jobs':jobs}, ensure_ascii=False, indent=2)+'\n')
    (OUT / 'SCIENCE_CHECK.json').write_text(json.dumps(dict(checks=checks, package_ready_sha256=digest(package/'READY.json'),
            package_sources=ready['source_shas'], source_manifest_sha256=digest(SOURCE/'jobs.json'),
            live_queue_modified=False, numerical_configuration_unchanged=True), ensure_ascii=False, indent=2)+'\n')
    (OUT / 'PREREG.json').write_text(json.dumps(dict(
        tasks=selected, method='temporal_gain_field', selected_before_new_outputs=True,
        selection='Book and handkerchief are the two remaining original user-selected core examples; follow-up to the fixed two pilots.',
        controls=['source', 'native', 'global_weak'], parameters_from='field_pilots',
        no_per_case_tuning=True, outcomes=['official nine numeric metrics', 'IS/CF AWQ separately', 'editing completion', 'frozen event frame offsets'],
        visual_rule='Freeze source/native/weak event intervals before viewing new outputs. Missing/changed event is not zero.',
        next_action='Deploy after current layer pilots and existing blend ownership are resolved; one video process on host41.'
    ), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'jobs':len(jobs), 'only_changed_nodes':['14','50'], 'live_queue_modified':False}))


if __name__ == '__main__':
    main()
