"""Exact source contract: frozen R6 candidate differs only by this pilot geometry."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GeometryContractTests(unittest.TestCase):
    def test_source_reconstructs_frozen_candidate(self):
        files = json.loads((ROOT / 'configs/candidate_parent_hashes.json').read_text())['files']
        self.assertEqual(files['extensions/H3FeedbackRouter/core.py'],
                         'afd1b6c3cc7892f0188d80490f8404a6a283351d75c70f9874339e1dd246be8a')
        replacements = {
            'extensions/H3FeedbackRouter/core.py': [
                ('(1024, 576, 141, 50, 65)', '(1312, 736, 141, 50, 65)'),
                ('frozen to 1024x576x141', 'frozen to 1312x736x141'),
                ('previously normal1024 source control; inspect independent early/final pose; no unseen generalization claim',
                 'known delayed example mechanism pilot; independent normal early validation pending')],
            'extensions/H3FeedbackRouter/observer.py': [('VIDEO_SHAPE = (1, 24, 42, 36, 64)', 'VIDEO_SHAPE = (1, 24, 42, 46, 82)')],
            'extensions/H3FeedbackRouter/__init__.py': [
                ('"width": ("INT", {"default": 1024})', '"width": ("INT", {"default": 1312})'),
                ('"height": ("INT", {"default": 576})', '"height": ("INT", {"default": 736})')],
        }
        for relative, expected in files.items():
            raw = (ROOT / relative).read_bytes()
            for new, old in replacements.get(relative, []):
                self.assertEqual(raw.count(new.encode()), 1, relative)
                raw = raw.replace(new.encode(), old.encode())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected, relative)

    def test_protocol_written_before_observation_remains_exact(self):
        self.assertEqual(hashlib.sha256((ROOT / 'configs/protocol.json').read_bytes()).hexdigest(),
                         'a2378d3af670d220937aa0ecc94314368baefc6094bfd658c1f3ad9aee267e38')

    def test_model_fingerprints_match_actual_parent_runtime(self):
        parent = json.loads((ROOT / 'configs/parent_runtime_provenance.json').read_text())
        fingerprints = json.loads((ROOT / 'configs/model_hashes_host9.json').read_text())
        for name, record in parent['models'].items():
            self.assertEqual(fingerprints[name]['sha256'], record['prior_full_sha256'])
            self.assertTrue(record['path'].startswith('/data5/researcher/ComfyUI/models/'))
            self.assertGreater(record['bytes'], 0)
        self.assertTrue(all(parent['core_matches'].values()))

if __name__ == '__main__':
    unittest.main()
