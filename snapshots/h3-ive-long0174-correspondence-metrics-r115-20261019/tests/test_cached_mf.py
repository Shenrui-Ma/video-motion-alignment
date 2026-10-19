import copy,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import read
from cached_mf import CASE,ACTUAL,validate_report

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.manifest=read(CASE/'INPUTS.json');self.report=read(ACTUAL/'tracks/native/REPORT.json')
    def reject(self,edit):
        report=copy.deepcopy(self.report);edit(report)
        with self.assertRaises(ValueError):validate_report(report,'native',self.manifest)
    def test_existing_official_settings(self):validate_report(self.report,'native',self.manifest)
    def test_checkpoint_change_rejected(self):self.reject(lambda r:r.update(checkpoint_sha256='f'*64))
    def test_window_change_rejected(self):self.reject(lambda r:r['tracker'].update(window_len=16))
    def test_sampling_change_rejected(self):self.reject(lambda r:r['score_frame_indices'].pop())
    def test_wrong_role_rejected(self):self.reject(lambda r:r.update(method='forced'))
    def test_pixel_change_rejected(self):self.reject(lambda r:r['decoded_frame_md5'].__setitem__(0,'changed'))
    def test_crop_change_rejected(self):
        self.manifest['crop_xywh']=[0,0,1280,720]
        with self.assertRaises(ValueError):validate_report(self.report,'native',self.manifest)

if __name__=='__main__':unittest.main()
