import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from verify_completed import check_record_semantics
from prelaunch_gates import check_layout_cases
from r50_contract import cases

class ProductionInterfaceTests(unittest.TestCase):
    def test_complete158_capture_and_legacy_rejection(self):
        parent=ROOT.parent/'h3-timing-auto-source28289-r45-20261017/configs/parent_captures.json'
        cap=json.loads(parent.read_text());case=cases()[0]
        cap['geometry']=case['geometry'];cap['run_id']=case['run_id']
        row=copy.deepcopy(cap['captures'][0]);row.update(geometry=case['geometry'],run_id=case['run_id'])
        check_record_semantics(row,cap,case)
        row['geometry']={'width':1312,'height':736,'frames':141,'fps':24}
        with self.assertRaises(ValueError):check_record_semantics(row,cap,case)

    def test_own_service_and_protocol_shape(self):
        import service
        from observer_import import t
        self.assertEqual(service.GPU,t.MAIN_UUID)
        self.assertEqual(service.RUN,t.REMOTE_ROOT)
        self.assertEqual(service.PORT,8518)
        self.assertEqual(len(cases()),5)
        for case in cases():
            geometry=t.geometry_for(case['run_id'])
            self.assertEqual(geometry.stream_shapes,((1,24,47,48,72),(1,32,2,263)))
            self.assertEqual(geometry.valid_frames,147)

if __name__=='__main__':unittest.main()
