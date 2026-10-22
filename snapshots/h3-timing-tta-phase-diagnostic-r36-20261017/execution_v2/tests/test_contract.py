import copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import contract
from view_output import inverse_pose

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value))

class ContractTests(unittest.TestCase):
    def test_default_entries_do_not_connect_or_import_models(self):
        for command in [['one_phase.py','--phase','pose:bad_004:flip'],['run_pose_phase.py','--item','bad_004','--view','flip'],['evaluate.py']]:
            p=subprocess.run([sys.executable,str(ROOT/'scripts'/command[0]),*command[1:]],capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr);self.assertIn('Prepared',p.stdout)
    def test_literal_authorization_and_phase_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'PROTOCOL.json').write_text('{}')
            for name in ['FREEZE.json','DESIGN_FREEZE.json']:write(root/name,{'files':{'PROTOCOL.json':digest(root/'PROTOCOL.json')}})
            base={'approved':True,'freeze_sha256':digest(root/'FREEZE.json'),'protocol_sha256':digest(root/'PROTOCOL.json'),'phases':['pose:bad_004:flip'],'gpu_allowed':False}
            with patch.object(contract,'ROOT',root):
                write(root/'AUTHORIZATION.json',base);contract.authorize('pose:bad_004:flip')
                for update in [{'approved':False},{'approved':1},{'freeze_sha256':'0'*64},{'gpu_allowed':True},{'phases':['evaluate']}]:
                    write(root/'AUTHORIZATION.json',base|update)
                    with self.assertRaises(ValueError):contract.authorize('pose:bad_004:flip')
    def test_changed_frozen_source_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'x.py').write_text('first')
            for name in ['FREEZE.json','DESIGN_FREEZE.json']:write(root/name,{'files':{'x.py':digest(root/'x.py')}})
            (root/'x.py').write_text('changed')
            with patch.object(contract,'ROOT',root):
                with self.assertRaises(ValueError):contract.validate_freeze()
    def test_wrong_video_source_rejected_before_pose_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/'x.mp4';video.write_bytes(b'wrong')
            entry={'local_video':str(video),'local_identity_pose':str(Path(tmp)/'pose.json'),'video_sha256':'0'*64}
            with self.assertRaises(ValueError):contract.video_pose_gate(entry)
    def test_no_person_reselection_or_ambiguous_frame_rescue(self):
        person={'coco17_xy':[[100.,100.]]*17,'coco17_score':[.9]*17,'box_xyxy':[50,50,150,200]}
        raw={'frames':[{'persons':[copy.deepcopy(person)],'selected_person':0,'selection_ambiguous':False}]}
        identity=copy.deepcopy(raw);identity['frames'][0]['selection_ambiguous']=True
        output=inverse_pose(raw,identity,'identity');frame=output['frames'][0]
        self.assertEqual(frame['selected_person'],0);self.assertEqual(frame['persons'][0]['coco17_score'],[0.]*17);self.assertEqual(frame['persons'][0]['r36_inverse_raw_scores'],[.9]*17)
    def test_different_selected_person_is_unknown(self):
        person={'coco17_xy':[[100.,100.]]*17,'coco17_score':[.9]*17,'box_xyxy':[50,50,150,200]}
        raw={'frames':[{'persons':[copy.deepcopy(person)],'selected_person':0,'selection_ambiguous':False}]};identity=copy.deepcopy(raw);identity['frames'][0]['persons'][0]['box_xyxy']=[700,500,850,700]
        out=inverse_pose(raw,identity,'identity');self.assertFalse(out['frames'][0]['r36_identity_correspondence']['valid'])

if __name__=='__main__':unittest.main()
