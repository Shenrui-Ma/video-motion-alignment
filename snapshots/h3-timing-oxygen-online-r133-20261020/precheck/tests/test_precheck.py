import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import precheck_support as s
from adult_selector import adult_only
from pose_domain import validate_pose


class FrozenScientificPrecheck(unittest.TestCase):
    def test_all_inherited_files_exact(self):
        for row in s.read(ROOT / 'configs/INHERITED.json'):
            self.assertEqual(s.sha(ROOT / row['file']), row['sha256'], row['file'])

    def test_only_actual_seed1703_ten_prefix_snapshots(self):
        c = s.config(); gate = s.read(ROOT / 'configs/R113_SEED1703_PAIR_GATE.json')
        self.assertEqual(c['snapshots'], gate['runs']['native']['snapshots'][:10])
        self.assertEqual(c['indices'], list(range(10)))
        self.assertEqual(c['seed'], 2026101703)
        self.assertFalse(c['formal_H3_authorized'])

    def test_actual_r81_controller_parity_first_ten(self):
        expected = s.read(ROOT / 'tests/R81_PARITY.json')
        controller = s.Controller(s.geometry(s.config()), arm='visible_only')
        decisions = []
        for n in range(10):
            file = ROOT / f'tests/fixtures/step{n:03d}.json.gz'
            observation = json.load(gzip.open(file, 'rt'))['observation']
            decision = controller.select(n, s.measurement(n, observation, 'a'*64, 'b'*64))
            wanted = expected['results']['visible_only'][n]
            self.assertEqual({key: decision[key] for key in wanted}, wanted)
            decisions.append(decision)
        self.assertEqual([n for n, row in enumerate(decisions) if s.stop_after(row)], [2, 3, 6, 7])

    def test_first_on_is_stop_and_requires_previous_evidence(self):
        controller = s.Controller(s.geometry(s.config()), arm='visible_only')
        observed = []
        for n in range(10):
            observation = json.load(gzip.open(ROOT / f'tests/fixtures/step{n:03d}.json.gz', 'rt'))['observation']
            decision = controller.select(n, s.measurement(n, observation, 'a'*64, 'b'*64))
            observed.append(n)
            if s.stop_after(decision):
                break
        self.assertEqual(observed, [0, 1, 2])
        self.assertEqual(decision['latent_bins'], [13, 14, 15, 16, 17])

    def test_order_cannot_skip_or_repeat(self):
        for bad in (1, 2, -1):
            controller = s.Controller(s.geometry(s.config()), arm='visible_only')
            with self.assertRaises(ValueError):
                controller.select(bad, {})

    def test_all_unknown_is_off_not_fallback(self):
        controller = s.Controller(s.geometry(s.config()), arm='visible_only')
        observation = json.load(gzip.open(ROOT / 'tests/fixtures/step000.json.gz', 'rt'))['observation']
        for n in range(10):
            o = copy.deepcopy(observation); o['physical_index'] = n; o['status'] = 'unknown_visibility'
            for row in o['windows']:
                row.update(baseline='unknown', status='baseline_unknown')
            decision = controller.select(n, s.measurement(n, o, 'a'*64, 'b'*64))
            self.assertFalse(decision['chosen_full']); self.assertEqual(decision['route_alpha'], 0)

    def test_incomplete_scan_rejected(self):
        observation = json.load(gzip.open(ROOT / 'tests/fixtures/step000.json.gz', 'rt'))['observation']
        observation['windows'].pop()
        with self.assertRaises(ValueError):
            s.Controller(s.geometry(s.config()), arm='visible_only').select(0, s.measurement(0, observation, 'a'*64, 'b'*64))

    def test_frozen_source_roi_and_valid_domain(self):
        c = s.config(); geom = s.geometry(c)
        filtered, _ = adult_only(s.read(ROOT / 'configs/source_raw.pose.json'), geom.video_geometry)
        self.assertEqual(filtered, s.read(ROOT / c['source_pose']))
        validate_pose(ROOT / c['source_pose'], geom)
        self.assertEqual(len(list(geom.windows()))*3, 120)
        self.assertEqual(geom.domain_record['excluded_padding_frames'], list(range(98, 107)))


class AdministrativeBoundaries(unittest.TestCase):
    def test_exact_user_service_is_preserved(self):
        c = s.config()['runtime']; user = c['preserved_user_service']
        row = dict(pid=user['pid'], uid=user['uid'], gpu_uuid=c['preserved_user_service_gpu'])
        with patch.object(s.lifetime, 'alive', return_value=True):
            s.validate_own_processes([row], c)

    def test_other_own_cuda_rejected(self):
        c = s.config()['runtime']
        with patch.object(s.lifetime, 'alive', return_value=True), self.assertRaises(ValueError):
            s.validate_own_processes([dict(pid=777, uid=1004, gpu_uuid=c['gpu_uuid'])], c)

    def test_reused_user_pid_rejected(self):
        c = s.config()['runtime']
        with patch.object(s.lifetime, 'alive', return_value=False), self.assertRaises(ValueError):
            s.validate_own_processes([], c)

    def test_foreign_processes_do_not_block_identity_gate(self):
        c = s.config()['runtime']
        with patch.object(s.lifetime, 'alive', return_value=True):
            s.validate_own_processes([dict(pid=777, uid=9999, gpu_uuid=c['gpu_uuid'])], c)

    def test_lingering_cuda_rejected(self):
        who = dict(pid=77, uid=1004, start_ticks=12, cmdline_sha256='a'*64)
        with patch.object(s.lifetime, 'alive', return_value=False), patch.object(s, 'apps', return_value=[dict(pid=77)]), self.assertRaises(ValueError):
            s.assert_released(who)

    def test_no_formal_authorization_in_precheck(self):
        self.assertEqual(s.config()['precheck_calls_DiT'], 0)
        self.assertNotIn('queue', s.config())


if __name__ == '__main__':
    unittest.main()
