import copy
import unittest
from contract import HERE, read
from manifest import reused_native_record

class RetryReuse(unittest.TestCase):
    def setUp(self):
        self.protocol = read(HERE / 'PROTOCOL.json')

    def test_five_native_records_preserved(self):
        original = read(HERE / 'audit/ORIGINAL_MANIFEST.json')
        for source in self.protocol['source_order']:
            actual = reused_native_record(self.protocol, source)
            expected = next(r for r in original['records'] if r['source_id'] == source and r['method'] == 'native')
            self.assertEqual({k: v for k, v in actual.items() if k != 'local_paths'},
                             {k: v for k, v in expected.items() if k != 'local_paths'})

    def test_changed_original_freeze_rejected(self):
        p = copy.deepcopy(self.protocol)
        p['native_reuse']['freeze_sha256'] = 'changed'
        with self.assertRaises(ValueError):
            reused_native_record(p, 'chest')

    def test_changed_original_protocol_rejected(self):
        p = copy.deepcopy(self.protocol)
        p['native_reuse']['protocol_sha256'] = 'changed'
        with self.assertRaises(ValueError):
            reused_native_record(p, 'chest')

    def test_retry_uses_new_attempt_path(self):
        p = self.protocol['methods']['automatic']
        self.assertIn('auto_r50_retry_', p['root_remote'])
        self.assertIn('auto-r50-retry-', p['root_local'])

if __name__ == '__main__':
    unittest.main()
