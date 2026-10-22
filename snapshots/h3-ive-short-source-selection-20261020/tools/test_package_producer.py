from pathlib import Path
import hashlib
import json
import tarfile
import tempfile
import unittest
from package_producer import deployment_files, package, verify_archive


class Packaging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'producer'
        (self.root / 'configs').mkdir(parents=True)
        (self.root / 'inputs').mkdir()
        (self.root / 'configs/queue.json').write_text(json.dumps({'jobs': ['native', 'forced'], 'finalize': True}))
        (self.root / 'configs/admission.json').write_text('{}')
        (self.root / 'configs/scientific_contract.json').write_text(json.dumps({'case_order': ['native', 'forced']}))
        video = self.root / 'inputs/video.mp4'
        video.write_bytes(b'fixture-video')
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        prepared = {'pairs': [{'files': {'video': {'file': 'inputs/video.mp4', 'sha256': sha(video)}}}]}
        (self.root / 'PREPARED_INPUTS_MANIFEST.json').write_text(json.dumps(prepared))
        files = {s: {'sha256': sha(self.root / s)} for s in ['configs/scientific_contract.json', 'PREPARED_INPUTS_MANIFEST.json']}
        (self.root / 'deploy_manifest.json').write_text(json.dumps({'files': files}))

    def test_includes_mutable_queue_and_separately_bound_input(self):
        output = Path(self.tmp.name) / 'payload.tar.gz'
        package(self.root, output)
        verify_archive(output, deployment_files(self.root))
        with tarfile.open(output) as tar:
            self.assertIn('configs/queue.json', tar.getnames())
            self.assertIn('inputs/video.mp4', tar.getnames())

    def test_missing_queue_refused_before_packaging(self):
        (self.root / 'configs/queue.json').unlink()
        with self.assertRaisesRegex(ValueError, 'queue.json'):
            deployment_files(self.root)

    def test_wrong_case_order_refused(self):
        (self.root / 'configs/queue.json').write_text(json.dumps({'jobs': ['forced', 'native'], 'finalize': True}))
        with self.assertRaisesRegex(ValueError, 'case order'):
            deployment_files(self.root)

    def test_old_archive_without_queue_is_rejected(self):
        expected = deployment_files(self.root)
        archive = Path(self.tmp.name) / 'incomplete.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name in expected:
                if name != 'configs/queue.json':
                    tar.add(self.root / name, arcname=name)
        with self.assertRaisesRegex(ValueError, 'queue.json'):
            verify_archive(archive, expected)


if __name__ == '__main__':
    unittest.main()
