import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('overlay_under_test', HERE / 'apply_overlay.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'
        self.root.mkdir()
        old_files = {'scripts/job.py': b'old job', 'scripts/run_queue.py': b'old controller',
                     'extensions/core.py': b'frozen science'}
        new_files = dict(old_files, **{'scripts/job.py': b'new job', 'scripts/run_queue.py': b'new controller'})
        def manifest(files):
            return json.dumps({'files': {k: {'sha256': m.sha(v), 'bytes': len(v)}
                                        for k, v in files.items()}}).encode()
        self.old, self.new = manifest(old_files), manifest(new_files)
        self.payload = {m.ADMIN + 'producer_before_restart/' + k: v for k, v in old_files.items()}
        self.payload[m.ADMIN + 'producer_before_restart/deploy_manifest.json'] = self.old
        self.payload.update({k: new_files[k] for k in m.CHANGED})
        self.payload['deploy_manifest.json'] = self.new
        for k, v in {**old_files, 'deploy_manifest.json': self.old}.items():
            p = self.root / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(v)
        (self.root / 'processes').mkdir()
        (self.root / 'processes/service.json').write_text(json.dumps({'pid': 123}))
        self.archive = Path(self.tmp.name) / 'overlay.tar.gz'
        self.pack()

    def pack(self):
        with tarfile.open(self.archive, 'w:gz') as tf:
            for name, data in self.payload.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

    def apply(self, exists=lambda pid: False):
        with patch.object(m, 'OLD', m.sha(self.old)), patch.object(m, 'NEW', m.sha(self.new)):
            return m.apply(self.root, self.archive, proc_exists=exists)

    def test_correct_overlay_preserves_original_snapshot(self):
        result = self.apply()
        self.assertTrue(result['passed'])
        self.assertEqual((self.root / 'deploy_manifest.json').read_bytes(), self.new)
        self.assertEqual((self.root / m.ADMIN / 'producer_before_restart/scripts/job.py').read_bytes(), b'old job')
        self.assertEqual((self.root / 'extensions/core.py').read_bytes(), b'frozen science')

    def test_live_pid_prevents_any_write(self):
        with self.assertRaisesRegex(RuntimeError, 'process still exists'):
            self.apply(lambda pid: True)
        self.assertEqual((self.root / 'scripts/job.py').read_bytes(), b'old job')

    def test_unexpected_science_change_is_rejected(self):
        (self.root / 'extensions/core.py').write_bytes(b'someone else edit')
        with self.assertRaisesRegex(RuntimeError, 'unexpected remote file mutation'):
            self.apply()
        self.assertEqual((self.root / 'scripts/job.py').read_bytes(), b'old job')

    def test_interrupted_known_admin_overlay_can_resume(self):
        (self.root / 'scripts/job.py').write_bytes(b'new job')
        self.assertTrue(self.apply()['passed'])
        self.assertTrue(self.apply()['passed'])

    def test_unsafe_tar_member_rejected_before_changes(self):
        self.payload['../outside'] = b'unsafe'
        self.pack()
        with self.assertRaisesRegex(RuntimeError, 'unsafe archive member'):
            self.apply()
        self.assertEqual((self.root / 'scripts/job.py').read_bytes(), b'old job')

    def test_old_snapshot_corruption_rejected(self):
        self.payload[m.ADMIN + 'producer_before_restart/extensions/core.py'] = b'bad snapshot'
        self.pack()
        with self.assertRaisesRegex(RuntimeError, 'original snapshot mismatch'):
            self.apply()


if __name__ == '__main__':
    unittest.main()
