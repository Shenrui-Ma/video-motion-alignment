"""Small synthetic artifact tests; no model or video computation."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import contract
import evaluate


def fixture(root):
    (root/'FREEZE.json').write_text('{}');dest=root/'results/evaluation';attempt=dest/'attempts/attempt001';attempt.mkdir(parents=True)
    (attempt/'SUMMARY.json').write_text('{}');dependencies={'case':{'video_sha256':'v','identity_pose_sha256':'p','views':{'flip':{'completion_sha256':'complete','inverse_pose_sha256':'inverse'}}}}
    record={'status':'complete','freeze_sha256':contract.sha(root/'FREEZE.json'),'attempt':'attempts/attempt001','input_dependencies':dependencies,'files':{'SUMMARY.json':contract.sha(attempt/'SUMMARY.json')}}
    (attempt/'VALIDATED.json').write_text(json.dumps(record));complete=record|{'attempt_manifest_sha256':contract.sha(attempt/'VALIDATED.json')};(dest/'COMPLETE.json').write_text(json.dumps(complete))
    return dest,attempt,dependencies


class EvaluationReuseTests(unittest.TestCase):
    def test_exact_complete_reuse_and_changed_upstream_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(evaluate,'ROOT',root):
                dest,attempt,deps=fixture(root);self.assertTrue(evaluate.verify_evaluation_complete(dest,deps))
                with self.assertRaisesRegex(ValueError,'upstream'):evaluate.verify_evaluation_complete(dest,{'case':{'changed':True}})
    def test_output_same_size_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(evaluate,'ROOT',root):
                dest,attempt,deps=fixture(root);(attempt/'SUMMARY.json').write_text('[]')
                with self.assertRaisesRegex(ValueError,'artifact'):evaluate.verify_evaluation_complete(dest,deps)
    def test_extra_file_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(evaluate,'ROOT',root):
                dest,attempt,deps=fixture(root);(attempt/'extra').write_text('x')
                with self.assertRaisesRegex(ValueError,'inventory'):evaluate.verify_evaluation_complete(dest,deps)
                (attempt/'extra').unlink();record=json.loads((dest/'COMPLETE.json').read_text());record['attempt']='../outside';(dest/'COMPLETE.json').write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError,'path'):evaluate.verify_evaluation_complete(dest,deps)
    def test_all_ten_view_inputs_required_before_evaluation_reuse(self):
        entries=[{'id':str(i),'video_sha256':'v','identity_pose_sha256':'p'} for i in range(5)]
        with patch.object(evaluate,'video_pose_gate',return_value=None),patch('phase_artifacts.completed_or_recover',return_value={'inverse_pose_sha256':'ip'}) as complete,patch('phase_artifacts.validate_record',return_value=None),patch.object(evaluate,'sha',return_value='sha'):
            got=evaluate.evaluation_dependencies(entries,False);self.assertEqual(len(got),5);self.assertEqual(complete.call_count,10)
        with patch.object(evaluate,'video_pose_gate',return_value=None),patch('phase_artifacts.completed_or_recover',return_value=None):
            with self.assertRaisesRegex(ValueError,'not complete'):evaluate.evaluation_dependencies(entries,False)


class ModelFileReuseTests(unittest.TestCase):
    def fixture(self,root):
        paths={'detector_path':root/'ckpts/yzd-v/DWPose/yolox_l.onnx','pose_path':root/'ckpts/hr16/DWPose/model.pt'}
        codes={'detector_code_sha256':root/'src/custom_controlnet_aux/dwpose/dw_onnx/cv_ox_det.py','pose_code_sha256':root/'src/custom_controlnet_aux/dwpose/dw_torchscript/jit_pose.py'}
        for p in [*paths.values(),*codes.values()]:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'frozen')
        prov={name:str(p) for name,p in paths.items()};prov.update({name.replace('_path','_sha256'):contract.sha(p) for name,p in paths.items()});prov.update({name:contract.sha(p) for name,p in codes.items()})
        return {'identity_provenance':prov},paths
    def test_model_code_hashes_checked_without_importing_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            e,paths=self.fixture(Path(tmp));self.assertEqual(len(contract.verify_model_files([e,e])),4);paths['pose_path'].write_bytes(b'change')
            with self.assertRaisesRegex(ValueError,'bytes changed'):contract.verify_model_files([e])
        self.assertNotIn('torch',sys.modules);self.assertNotIn('onnxruntime',sys.modules)
    def test_conflicting_historical_model_binding_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            e,_=self.fixture(Path(tmp));bad={'identity_provenance':e['identity_provenance']|{'pose_sha256':'changed'}}
            with self.assertRaisesRegex(ValueError,'Conflicting'):contract.verify_model_files([e,bad])

if __name__=='__main__':unittest.main()
