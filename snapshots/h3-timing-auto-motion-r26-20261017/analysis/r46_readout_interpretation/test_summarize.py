"""Arithmetic checks for descriptive weights/divergence; no production claims."""
import unittest
import tempfile
import json
from pathlib import Path
import numpy as np
from summarize import frame_weights, weighted_mean, js_divergence, require, bind_report, digest


class SummaryMathTests(unittest.TestCase):
    def test_partial_physical_bin_coverage(self):
        intervals = [[0, 0], [1, 4], [5, 8]]
        np.testing.assert_array_equal(frame_weights(intervals, [3, 6]), [0, 2, 2])
        self.assertEqual(weighted_mean(np.array([9., 2., 4.]), np.array([0., 2., 2.])), 3.)

    def test_js_equal_and_disjoint(self):
        p = np.array([[1., 0.], [.5, .5]])
        np.testing.assert_allclose(js_divergence(p, p), [0., 0.], atol=0)
        np.testing.assert_allclose(js_divergence(p[:1], np.array([[0., 1.]])), [np.log(2)])

    def test_full_minus_known_partitions_physical_duration(self):
        spans = [(1, 4, 4, 4, 4)[i % 5] for i in range(42)]
        cursor = 0; intervals = []
        for span in spans:
            intervals.append([cursor, cursor + span - 1]); cursor += span
        full = frame_weights(intervals, [0, 140]); known = frame_weights(intervals, [44, 59])
        self.assertEqual(full.sum(), 141)
        self.assertEqual(known.sum(), 16)
        self.assertEqual((full - known).sum(), 125)
        self.assertTrue((full >= known).all())

    def test_invalid_support_is_rejected(self):
        with self.assertRaises(ValueError):
            weighted_mean(np.array([1., 2.]), np.zeros(2))
        with self.assertRaises(ValueError):
            require(False, 'failed endpoint')

    def test_wrong_state_and_missing_endpoint_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = root / 'audit/probe/bad'; folder.mkdir(parents=True)
            for filename in ['attention.pt', 'endpoint_raw.pt']:
                (folder / filename).write_bytes(filename.encode())
            source = {'source_run': 'original-bad', 'seed': 11,
                      'raw_input': {'packed_signature': 'input'}, 'condition': {'sha256': 'cond'}}
            report = {'label': 'bad', 'source_run': 'original-bad', 'seed': 11,
                      'raw_input_signature': 'input', 'condition_sha256': 'cond',
                      'protocol_sha256': 'protocol', 'source_binding_sha256': 'source',
                      'endpoint_sha256': digest(folder/'endpoint_raw.pt'),
                      'probe': {'file_sha256': digest(folder/'attention.pt')}}
            (folder/'report.json').write_text(json.dumps(report))
            record = {'state': 'bad', 'historical_endpoint_independently_exact': True,
                      'DiT_NFE': 1, 'Euler_updates': 0,
                      'report_sha256': digest(folder/'report.json'),
                      'attention_sha256': digest(folder/'attention.pt'),
                      'endpoint_sha256': digest(folder/'endpoint_raw.pt')}
            bind_report(root, 'bad', source, report, record, 'protocol', 'source')
            with self.assertRaisesRegex(ValueError, 'label'):
                bind_report(root, 'normal', source, report, record, 'protocol', 'source')
            with self.assertRaisesRegex(ValueError, 'source state'):
                bind_report(root, 'bad', dict(source, seed=13), report, record, 'protocol', 'source')
            (folder/'endpoint_raw.pt').unlink()
            with self.assertRaisesRegex(ValueError, 'endpoint_raw.pt'):
                bind_report(root, 'bad', source, report, record, 'protocol', 'source')


if __name__ == '__main__':
    unittest.main()
