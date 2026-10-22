"""CPU-only 2+2 fixtures: real immutable prefix, synthetic future target receipts."""
import copy
import tempfile
import unittest
from pathlib import Path
from common import ROOT, read, write, bound, expected_router
from finalize_composite import ARMS, SCHEMA, verify_composite_record, validate_migration
from hardware_prefix import hardware_files, verify_hardware_prefix


class HardwareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'audit')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        manifest = read(ROOT / 'EVALUATION_MANIFEST.json')
        self.case = next(c for c in manifest['cases'] if c['source_id'] == 'short_0358')
        self.prefix = ROOT / 'audit/hardware_recovery/prefix_evidence'
        migration = read(self.prefix / 'MIGRATION_MANIFEST.json')
        self.bindings = {a: read(ROOT / 'runtime/short_0358' / (a + '.json')) for a in ARMS}
        self.runs = {a: read(ROOT / 'actual/short_0358' / a / 'GATE.json') for a in ARMS[:2]}
        new_binding = self.bindings['global_weak']
        self.owner = {'pid': 9001, 'identity': {'uid': 1004, 'start_ticks': '123'},
                      'port': new_binding['port'], 'gpu_uuid': new_binding['gpu_uuid']}
        for arm in ARMS[2:]:
            run = copy.deepcopy(self.runs['early'])
            binding = self.bindings[arm]
            router = expected_router(self.case, {'id': arm})
            run.update(run_id=binding['run_id'], role=arm, service_owner=self.owner,
                       producer_seal_sha256=binding['producer_seal']['sha256'],
                       actual_routed_steps_zero_based=binding['steps_0based'],
                       routed_blocks=len(binding['steps_0based']) * 50, alpha=router['alpha'],
                       physical_query_window=[router['start_frame'], router['end_frame']])
            run['video'] = {'file': binding['remote_root'] + '/output/' + binding['run_id'] + '.mp4'}
            run['sampler_timing']['run_id'] = binding['run_id']
            self.runs[arm] = run
        migration_file = bound(self.prefix / 'MIGRATION_MANIFEST.json')
        segment = {'schema': 'r149-fixed-schedule-segment-gate-v1', 'passed': True,
                   'source_id': 'short_0358', 'segment_id': 'drink_split_global_host41',
                   'migration_manifest_sha256': migration_file['sha256'],
                   'same_persistent_service': True, 'phase_displacement': 0,
                   'producer_seal_sha256': new_binding['producer_seal']['sha256'],
                   'runs': {a: self.runs[a] for a in ARMS[2:]}, 'service_owner': self.owner}
        segment_file = self.store('segment', segment)
        complete = {'schema': 'r149-schedule-segment-completion-v1', 'passed': True,
                    'segment_id': segment['segment_id'], 'migration_manifest_sha256': migration_file['sha256'],
                    'jobs': [self.runs[a]['run_id'] for a in ARMS[2:]], 'remaining': [],
                    'GPU_released': True, 'service_owner': self.owner, 'runtime_gate_sha256': segment_file['sha256']}
        release = {'owner': self.owner, 'passed': True, 'process_absent': True, 'CUDA_allocation_absent': True,
                   'cleanup': {'pid': self.owner['pid'], 'process_absent': True, 'own_compute_absent': True}}
        self.record = {'schema': SCHEMA, 'passed': True, 'source_id': 'short_0358',
                       'same_persistent_service': False, 'original_four_arm_COMPLETE': False,
                       'migration': migration_file, 'deployment': bound(self.prefix / 'MIGRATION_DEPLOYMENT.json'),
                       'partial_release': bound(self.prefix / 'PREFIX_PARTIAL_RELEASE.json'),
                       'segment_gate': segment_file, 'segment_complete': self.store('complete', complete),
                       'segment_release': self.store('release', release),
                       'bindings': {a: self.store('binding_' + a, b) for a, b in self.bindings.items()},
                       'job_gates': {a: (bound(ROOT / 'actual/short_0358' / a / 'GATE.json') if a in ARMS[:2]
                                         else self.store('gate_' + a, r)) for a, r in self.runs.items()},
                       'partial_artifacts': {k: bound(self.prefix / rel) for k, rel in hardware_files(migration).items()}}

    def store(self, name, data):
        path = self.folder / (name + '.json')
        write(path, data)
        return bound(path)

    def change(self, key, mutate):
        data = read(self.record[key]['file'])
        mutate(data)
        self.record[key] = self.store(key + '_changed', data)
        if key == 'partial_release':
            deployment = read(self.record['deployment']['file'])
            deployment['prefix_partial_release_sha256'] = self.record[key]['sha256']
            self.record['deployment'] = self.store('deployment_updated', deployment)

    def rejects(self):
        with self.assertRaises(ValueError):
            verify_composite_record(self.record, self.case)

    def test_real_prefix_and_synthetic_two_arm_target_accept(self):
        self.assertEqual(verify_composite_record(self.record, self.case), self.record)
        self.assertIsNone(read(self.record['partial_release']['file'])['CUDA_allocation_absent'])

    def test_no_old_cleanup_file_is_required(self):
        self.assertNotIn('cleanup', self.record['partial_artifacts'])
        self.assertTrue(verify_composite_record(self.record, self.case))

    def test_hardware_unknown_cannot_be_claimed_released(self):
        self.change('partial_release', lambda r: r.update(CUDA_allocation_absent=True))
        self.rejects()

    def test_missing_unknown_field_rejected(self):
        self.change('partial_release', lambda r: r.pop('CUDA_allocation_absent'))
        self.rejects()

    def test_new_gpu_unknown_rejected(self):
        self.change('segment_release', lambda r: r.update(CUDA_allocation_absent=None))
        self.rejects()

    def test_old_prefix_cannot_claim_complete(self):
        self.change('partial_release', lambda r: r.update(original_four_arm_COMPLETE=True, remaining_runs=[]))
        self.rejects()

    def test_missing_role_rejected(self):
        del self.record['job_gates']['split']
        self.rejects()

    def test_two_segments_cannot_claim_same_service(self):
        self.record['same_persistent_service'] = True
        self.rejects()

    def test_missing_cleanup_failure_rejected(self):
        key = next(k for k in self.record['partial_artifacts'] if k.endswith('/CLEANUP_FAILURE.json'))
        del self.record['partial_artifacts'][key]
        self.rejects()

    def test_original_failure_sha_mismatch_rejected(self):
        key = next(k for k in self.record['partial_artifacts'] if k.endswith('/FAILURE.json'))
        self.record['partial_artifacts'][key] = self.store('forged_failure', {'error': 'root admission pending'})
        self.rejects()

    def test_wrong_source_owner_rejected(self):
        self.change('partial_release', lambda r: r.update(service_owner=self.owner))
        self.rejects()

    def test_wrong_target_release_owner_rejected(self):
        self.change('segment_release', lambda r: r.update(owner=self.runs['early']['service_owner']))
        self.rejects()

    def test_wrong_gate_sha_rejected(self):
        self.change('partial_release', lambda r: r['gates'][self.runs['early']['run_id']].update(sha256='0' * 64))
        self.rejects()

    def test_target_segment_cannot_omit_split(self):
        self.change('segment_gate', lambda r: r['runs'].pop('split'))
        self.rejects()

    def test_wrong_target_deployment_seal_rejected(self):
        self.change('deployment', lambda r: r['segments']['host41_recovery'].update(producer_seal_sha256='f' * 64))
        self.rejects()

    def test_target_roles_must_share_actual_owner(self):
        self.runs['split']['service_owner'] = dict(self.owner, pid=9002)
        self.record['job_gates']['split'] = self.store('wrong_split_owner', self.runs['split'])
        self.rejects()


if __name__ == '__main__':
    unittest.main()
