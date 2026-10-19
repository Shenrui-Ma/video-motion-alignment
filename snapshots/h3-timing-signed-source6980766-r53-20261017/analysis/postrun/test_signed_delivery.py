import copy
import unittest
from pathlib import Path

import contract as c
import presentation


class SignedDeliveryTests(unittest.TestCase):
    def test_signed_proposal_direction(self):
        delayed = {'lags': {'0.3': 4, '0.5': 5}, 'direction': 'delayed'}
        advanced = {'lags': {'0.3': -4, '0.5': -5}, 'direction': 'advanced'}
        self.assertEqual(c.signed_directions([delayed, advanced]), ['delayed', 'advanced'])
        for item in [dict(advanced, direction='delayed'),
                     {'lags': {'0.3': -4, '0.5': 5}, 'direction': 'advanced'},
                     {'lags': {'0.3': -4, '0.5': float('nan')}, 'direction': 'advanced'}]:
            with self.assertRaises(ValueError):
                c.signed_directions([item])

    def test_caption_columns_bind_actual_methods(self):
        p = c.read(c.HERE / 'PROTOCOL.json')
        layout = p['presentation']
        self.assertEqual(presentation.layout_keys({'SOURCE': 1, 'native': 2, 'AUTO': 3}, layout),
                         ['SOURCE', 'native', 'AUTO'])
        with self.assertRaises(ValueError):
            presentation.layout_keys({'SOURCE': 1, 'native': 2}, layout)
        self.assertEqual(c.sha(c.HERE / layout['asset']), layout['asset_sha256'])

    def test_actual_r47_parent_bytes_and_producer_seal(self):
        p = c.read(c.HERE / 'PROTOCOL.json')
        root = Path(p['root_local'])
        self.assertEqual(c.sha(root / 'deploy_manifest.json'), p['producer_manifest_sha256'])
        self.assertEqual(c.sha(root / 'configs/protocol.json'), p['producer_protocol_sha256'])
        for name, parent in p['parents'].items():
            self.assertEqual(c.sha(c.HERE / parent['pose']), parent['pose_sha256'])
            self.assertEqual(c.sha(c.HERE / parent['job']), parent['job_sha256'])
        self.assertEqual(c.sha(root / p['source_pose']), p['source_pose_sha256'])


if __name__ == '__main__':
    unittest.main()
