import hashlib, tempfile, unittest
from pathlib import Path
import recover

class RecoveryTests(unittest.TestCase):
    def test_actual_dictionary_key_both_orders(self):
        videos = {'SOURCE': 's', 'native': 'n', 'fixed_full': 'f', 'AUTO': 'a'}
        self.assertEqual(recover.blind_videos(videos, ['auto', 'fixed_full']), {'A': 'a', 'B': 'f'})
        self.assertEqual(recover.blind_videos(videos, ['fixed_full', 'auto']), {'A': 'f', 'B': 'a'})

    def test_unregistered_arm_rejected(self):
        with self.assertRaises(ValueError): recover.blind_videos({}, ['native', 'auto'])

    def fixture(self, p):
        rows = []
        for i in range(32):
            f = p / f'{i}.txt'; f.write_bytes(str(i).encode())
            rows.append({'relative': f.name, 'bytes': f.stat().st_size, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()})
        return rows

    def test_exact_partial_success(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); rows = self.fixture(p); recover.check_partial(p, rows, exact=True)

    def test_changed_or_missing_partial_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); rows = self.fixture(p); (p / '0.txt').write_text('different')
            with self.assertRaises(ValueError): recover.check_partial(p, rows)
            (p / '0.txt').unlink()
            with self.assertRaises(ValueError): recover.check_partial(p, rows)

    def test_extra_file_and_duplicate_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); rows = self.fixture(p); (p / 'unexpected').write_text('x')
            with self.assertRaises(ValueError): recover.check_partial(p, rows, exact=True)
            with self.assertRaises(ValueError): recover.check_partial(p, rows[:-1] + [rows[0]])

    def test_final_extensions_preserve_original_partial(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); rows = self.fixture(p); (p / 'new-summary').write_text('x')
            recover.check_partial(p, rows)

if __name__ == '__main__': unittest.main()
