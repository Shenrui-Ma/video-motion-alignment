import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'extensions'), str(ROOT/'scripts')]
from H3EventAudit import H3EventAuditNoise, audit_root
from H3TemporalRouter import core, validate_run_contract
from H3TemporalRouter.layout import event_latent_range
from preflight import check, expected_graph, admission_document, REMOTE, RUN_ID
import service


def dense(q, k, v):
    z = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return z.softmax(-1) @ v, z.logsumexp(-1)


class ContractTests(unittest.TestCase):
    def test_exact_graph_aux_paths_pins_and_queue(self):
        self.assertTrue(check(ROOT)['passed'])
        graph = json.loads((ROOT/'configs'/f'{RUN_ID}.json').read_text())
        with patch.object(Path, 'mkdir'):
            noise = H3EventAuditNoise().get_noise(**graph['6']['inputs'])
            self.assertEqual(len(noise), 1)
            self.assertEqual(str(audit_root(graph['5']['inputs']['audit_dir'])), REMOTE+'/audit')
        args = {k: v for k, v in graph['50']['inputs'].items() if k not in ('model', 'positive')}
        validate_run_contract(**args)
        for key, bad in [('step_end', 15), ('run_id', 'wrong'), ('alpha', .5), ('radius', 1),
                         ('audit_dir', REMOTE+'/../bad')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_run_contract(**dict(args, **{key: bad}))
        for path in ('/tmp', '/data5/researcher/h3_runs/timing_spatial_r3_20261016/audit',
                     REMOTE+'/../bad'):
            with self.assertRaises(ValueError): audit_root(path)
        self.assertEqual(event_latent_range(50, 65, 42), (14, 20))

    def test_runtime_constants_and_real_readiness_name(self):
        self.assertEqual(str(service.RUN), REMOTE)
        self.assertEqual(service.PORT, 8482)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        command = service.command()
        self.assertIn('H3TemporalRouter', command)
        self.assertNotIn('H3PhaseRoPE', command)
        launcher = (ROOT/'scripts/launch_remote.py').read_text()
        self.assertIn('/object_info/H3TemporalRouter', launcher)
        self.assertIn("assert 'H3TemporalRouter' in info", launcher)
        self.assertNotIn("('H3TemporalRouter',", launcher)

    def test_x0_core_identical_R18(self):
        source=json.loads((ROOT/'configs/source_original_hashes.json').read_text())
        rel='extensions/H3X0Readout/core.py'
        self.assertEqual(source[rel]['source_sha256'],source[rel]['current_sha256'])
        self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),source[rel]['source_sha256'])

    def test_normal_seed_and_graph_match_except_operator_admin(self):
        graph = json.loads((ROOT/'configs'/f'{RUN_ID}.json').read_text())
        parent = json.loads((ROOT/'configs/parent_normal_graph.json').read_text())
        self.assertEqual(graph['6']['inputs']['noise_seed'], 2026101313)
        self.assertEqual(parent['6']['inputs']['noise_seed'], 2026101313)
        for node in graph:
            if node == '50': continue
            a, b = copy.deepcopy(graph[node]), copy.deepcopy(parent[node])
            for key in ('audit_dir', 'source_audit_dir', 'output_dir', 'pair_id', 'run_id', 'source_run_id', 'filename_prefix'):
                if key in a['inputs']: a['inputs'][key] = b['inputs'][key]
            self.assertEqual(a,b, node)
        wrong=copy.deepcopy(graph); wrong['6']['inputs']['noise_seed']=2026101311
        self.assertNotEqual(wrong, expected_graph(json.loads((ROOT/'configs/parent_full_graph.json').read_text())))

    def test_unapproved_or_unknown_admission_rejected(self):
        with self.assertRaises(ValueError): admission_document(ROOT, approved=True)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder); (target/'configs').mkdir()
            for name in ('admission.json','admission_template.json'):
                (target/'configs'/name).write_bytes((ROOT/'configs'/name).read_bytes())
            v=json.loads((target/'configs/admission.json').read_text());v['unexpected']=True
            (target/'configs/admission.json').write_text(json.dumps(v))
            with self.assertRaises(ValueError):admission_document(target)

    def test_exact_other_owned_pid_admission_and_stale_rejection(self):
        who={'uid':service.os.getuid(),'start_ticks':'123','cmdline_sha256':'a'*64}
        admission={'scope':'own_user_video_jobs','permitted_compute_processes':[{'pid':99,'identity':who}]}
        process=[{'pid':99,'gpu_uuid':'different-card'}]
        queue={'queue_running':[],'queue_pending':[]}
        with patch.object(service,'proc_uid',return_value=service.os.getuid()),patch.object(service,'external_identity',return_value=who):
            service.check_admission(admission,process,queue)
        for actual in (None,dict(who,start_ticks='124')):
            with patch.object(service,'proc_uid',return_value=service.os.getuid()),patch.object(service,'external_identity',return_value=actual):
                with self.assertRaises(RuntimeError):service.check_admission(admission,process,queue)

    def test_schedule_runs1000blocks300routed_and_keeps_qkv_rng(self):
        torch.set_num_threads(1)
        gen = torch.Generator().manual_seed(18)
        q, k, v = [torch.randn(1, 2, 29, 8, generator=gen) for _ in range(3)]
        original = [x.clone() for x in (q, k, v)]
        plan = {'reference_video_segment': [3, 15], 'query_interval_half_open': [20, 26],
                'latent_interval_half_open': [1, 3], 'frame_rows': 3, 'seq_len': 29}
        real_route = core.route_attention
        def cpu_route(*args, **kwargs): return real_route(*args, **kwargs, attention=dense)
        def attention_pytorch(*args, **kwargs): raise AssertionError('unused entry identity')
        layout = object()
        with tempfile.TemporaryDirectory() as folder:
            state = core.RouterState({}, 'mass_preserve', 1., 0, 0, 50, 65, 0, 50, 6, 12, 'test', folder)
            state.plan_for = lambda _: plan
            patches = [core.EventBlockPatch(state, b) for b in range(50)]
            def block(args):
                override = args['transformer_options']['optimized_attention_override']
                return override(attention_pytorch, q, k, v, 2, skip_reshape=True)
            native = real_route(q, k, v, 2, plan, mode='native', attention=dense)
            full = real_route(q, k, v, 2, plan, mode='mass_preserve', attention=dense)
            rng = torch.get_rng_state().clone()
            with patch.object(core, 'route_attention', side_effect=cpu_route), \
                    patch.object(core, 'component_probe', return_value={}), \
                    patch.object(core, 'temporal_readout', return_value={}):
                for step in range(20):
                    for b in range(50):
                        options = {'block_index': b, 'minimax_h3_layout': layout,
                                   'sample_sigmas': torch.linspace(1, 0, 21)}
                        out = patches[b]({'layout': layout, 'transformer_options': options},
                                         {'original_block': block})
                        self.assertTrue(torch.equal(out, full if 6 <= step < 12 else native))
                        self.assertNotIn('optimized_attention_override', options)
            self.assertEqual(state.audit['completed_calls'], 1000)
            self.assertEqual(state.audit['completed_forward_calls'], 20)
            self.assertEqual(state.audit['calls_by_forward'], [50]*20)
            self.assertEqual(state.audit['routed_by_forward'], [0]*6+[50]*6+[0]*8)
            self.assertEqual(state.audit['routed_calls'], 300)
            self.assertEqual(state.audit['routed_by_block'], [6]*50)
            self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        for before, after in zip(original, (q, k, v)): self.assertTrue(torch.equal(before, after))


if __name__ == '__main__': unittest.main()
