"""Build isolated paired pilots without changing prompts or the running queue."""
import copy
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
E = P.parents[2]
SOURCE = E / 'innovation/pilot_ten/other_packages/temporal_coverage_v2/host41'
REMOTE = '/data4/research-user/h3_runs/benchmark_schedule_20261022'


def load(path):
    return json.loads(path.read_text())


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    existing = P / 'handoff_request.json'
    if (P / 'PUBLISHED.json').exists() or (existing.exists() and load(existing).get('status') == 'ready'):
        raise RuntimeError('Published batch: preserve unique host ownership; update the staged handoff explicitly')
    base = load(P / 'base_manifest.json')
    assert len(base['jobs']) == 56
    jobs = []
    # Independent modules first. A fixed stronger-dose control distinguishes
    # dynamic allocation from a benefit obtained by simply increasing alpha.
    methods = ('dynamic_dof', 'heads_budget', 'coverage_blend25', 'fixed0375')
    for method in methods:
        for old_job in load(SOURCE / 'jobs.json')['jobs']:
            job = copy.deepcopy(old_job)
            graph = load(SOURCE / job['graph'])
            old_graph = copy.deepcopy(graph)
            task = job['metadata']['task_id']
            jid = 'adapt41_' + task + '_' + method
            old_inputs = graph['50']['inputs']
            common = {k: copy.deepcopy(old_inputs[k]) for k in (
                'model', 'positive', 'enabled', 'start_frame', 'end_frame',
                'run_id', 'block_start', 'block_end', 'step_start', 'step_end')}
            if method == 'coverage_blend25':
                graph['50']['class_type'] = 'H3TemporalCoverageBlend'
                params = {**old_inputs, 'coverage_mix': .25,
                          'audit_dir': REMOTE + '/audit/coverage_blend'}
                formula = 'O + .25*m_ref*((.75*I+.25*P)@S_reference - R_all)'
            else:
                graph['50']['class_type'] = 'H3FeatureGuidance'
                mode = {'dynamic_dof': 'dynamic_strength_dof',
                        'heads_budget': 'heads_budget', 'fixed0375': 'fixed'}[method]
                params = {**common, 'mode': mode, 'alpha_prior': .375 if mode == 'fixed' else .25,
                          'alpha_max': .5, 'prior_weight': 1., 'collateral': 1.,
                          'probes': 8, 'basis': 'centered',
                          'audit_dir': REMOTE + '/audit/feature_guidance'}
                formula = 'O + alpha(layer,step,head)*m_ref*(S_same - R_all)'
            graph['50']['inputs'] = params
            graph['14']['inputs']['filename_prefix'] = jid + '/{attempt_id}'
            # Every non-treatment node remains byte-for-byte structurally equal.
            assert {k: v for k, v in graph.items() if k not in ('50', '14')} == {
                k: v for k, v in old_graph.items() if k not in ('50', '14')}
            job.update(max_attempts=1, id=jid, graph='graphs/' + jid + '.json', expected_output_prefix=jid + '/')
            meta = job['metadata']
            for obsolete in ('coverage_unit', 'routing_constraints', 'solver', 'solver_change',
                             'preserved_v1_result', 'fallback_policy'):
                meta.pop(obsolete, None)
            meta.update(cohort='adaptive_research_20261023', method=method,
                        innovation_parameters=params, attention_formula=formula,
                        innovation_status='cpu_checks_pending',
                        comparison_scope='same historical prompt/seed/cache/model/geometry; reused native/global_weak',
                        reference_source_job=old_job['id'],
                        strength_scope='pre-output-projection attention correction')
            if method == 'dynamic_dof':
                meta['calibration'] = 'rank-one temporal variance vs D-1 complement; isotropic null alpha=.25'
                meta['alpha_scope'] = 'current layer and denoising step; one scalar shared across heads'
            if method == 'heads_budget':
                meta['budget'] = 'sum_h alpha_h^2 ||D_h||^2 = .25^2 sum_h ||D_h||^2 before W_o'
            write(P / job['graph'], graph)
            meta['graph_sha256'] = sha(P / job['graph'])
            jobs.append(job)
    assets = []
    for local, remote, names in (
        ('feature_guidance', 'H3FeatureGuidance', ('__init__.py','nodes.py','attention.py','controller.py','frozen.py')),
        ('coverage_blend', 'H3TemporalCoverageBlend', ('__init__.py','nodes.py','attention.py','routing.py','frozen.py'))):
        for name in names:
            path = E / 'innovation' / local / name
            assets.append({'path': REMOTE + '/custom_nodes/' + remote + '/' + name,
                           'sha256': sha(path), 'local': str(path)})
    for j in jobs:
        assets.append({'path': REMOTE + '/' + j['graph'], 'sha256': sha(P / j['graph']),
                       'local': str(P / j['graph'])})
    old = (P / 'manage_service.before.py').read_text()
    assert "'H3TemporalCoverageV2'" in old
    new = old.replace("'H3TemporalCoverageV2'", "'H3TemporalCoverageV2','H3TemporalCoverageBlend','H3FeatureGuidance'")
    compile(new, 'manage_service.after.py', 'exec')
    (P / 'manage_service.after.py').write_text(new)
    staged = REMOTE + '/scripts/manage_service.adaptive20261023.staged.py'
    assets.append({'path': staged, 'sha256': sha(P / 'manage_service.after.py'),
                   'local': str(P / 'manage_service.after.py')})
    change = {'path': REMOTE + '/scripts/manage_service.py', 'staged_path': staged,
              'before_sha256': sha(P / 'manage_service.before.py'),
              'after_sha256': sha(P / 'manage_service.after.py')}
    request = {'status': 'tests_pending', 'cpu_tests': {'passed': False}, 'base': base,
               'pilots': {'jobs': jobs}, 'assets': assets, 'service_change': change}
    write(P / 'jobs.json', {'jobs': jobs})
    write(P / 'handoff_request.json', request)
    print(json.dumps({'base': len(base['jobs']), 'new': len(jobs), 'status': request['status']}))


if __name__ == '__main__':
    build()
