import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import adapter
import run_once

SYNTH=adapter.module_at(adapter.BASE/'phase_shape_profile_candidate_v1/synthetic.py','frozen_synthetic')
CORE=adapter.module_at(adapter.KERNEL,'frozen_math_for_comparison')


def pose_fixture(torso_conf=1):
    features=SYNTH.features('identifiable')
    records=[]
    for i,directions in enumerate(features['directions']):
        xy=np.zeros((17,2));xy[5]=[-1,0];xy[6]=[1,0];xy[11]=[-.7,2];xy[12]=[.7,2]
        xy[7]=xy[5]+directions[0];xy[9]=xy[7]+directions[1]
        xy[8]=xy[6]+directions[2];xy[10]=xy[8]+directions[3]
        conf=np.ones(17);conf[[11,12]]=torso_conf
        records.append({'frame':i,'time_s':i/24,'selected_person':0,
                        'persons':[{'coco17_xy':xy.tolist(),'coco17_score':conf.tolist()}]})
    return {'video':{'fps':24},'frames':records}


class AdapterTests(unittest.TestCase):
    def test_frozen_math_equivalence(self):
        a=SYNTH.features('identifiable');b=SYNTH.features('identifiable',6,SYNTH.ROTATION)
        direct,original=CORE.analyze(a,b)
        wrapped,evidence=adapter.analyze({h:a for h in adapter.THRESHOLDS},{h:b for h in adapter.THRESHOLDS})
        self.assertEqual(direct['selected'],wrapped['selected'])
        self.assertEqual(direct['parts'],wrapped['parts'])
        for name,array in original.items():np.testing.assert_array_equal(array,evidence[name])
        self.assertIn('left_arm__h0.3__raw_zero',evidence)
        self.assertIn('right_arm__h0.5__mask',evidence)

    def test_actual_converter_on_synthetic_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            path=Path(directory)/'synthetic.json';path.write_text(json.dumps(pose_fixture()))
            converted,failures=adapter.load(path)
            self.assertEqual(failures,{})
            for h in adapter.THRESHOLDS:
                np.testing.assert_allclose(converted[h]['directions'],SYNTH.features('identifiable')['directions'],atol=1e-14)
                np.testing.assert_array_equal(converted[h]['confidence'],np.ones((141,4)))

    def test_threshold_specific_missing_torso(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            path=Path(directory)/'synthetic.json';path.write_text(json.dumps(pose_fixture(.4)))
            converted,failures=adapter.load(path)
            self.assertEqual(list(failures),['0.5'])
            self.assertTrue(np.isfinite(converted[.3]['directions']).all())
            self.assertTrue(np.isnan(converted[.5]['directions']).all())
            result,evidence=adapter.analyze(converted,converted)
            self.assertEqual(result['K'],0)
            self.assertTrue(evidence['left_arm__h0.3__mask'].any())
            self.assertFalse(evidence['left_arm__h0.5__mask'].any())

    def test_raw_nonfinite_joint_is_not_hidden_by_min(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            value=pose_fixture();person=value['frames'][70]['persons'][0]
            person['coco17_score'][7]=float('inf')
            path=Path(directory)/'synthetic.json';path.write_text(json.dumps(value))
            converted,_=adapter.load(path)
            for h in adapter.THRESHOLDS:
                self.assertTrue(np.isnan(converted[h]['directions'][70,:2]).all())
                self.assertTrue((converted[h]['confidence'][70,:2]==0).all())

    def test_finite_confidence_above_one_retained(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            value=pose_fixture()
            for frame in value['frames']:
                frame['persons'][0]['coco17_score']=[1.2]*17
            path=Path(directory)/'synthetic.json';path.write_text(json.dumps(value))
            converted,_=adapter.load(path)
            for h in adapter.THRESHOLDS:
                np.testing.assert_array_equal(converted[h]['confidence'],np.full((141,4),1.2))
            result,evidence=adapter.analyze(converted,converted)
            self.assertAlmostEqual(evidence['left_arm__h0.5__weight'][24,116],1.2*93*2,places=10)
            a,b=np.indices((141,141));family=(b-a+1)>=8
            for part in ('left_arm','right_arm'):
                self.assertTrue(np.isfinite(evidence[part+'__J'][family]).all())
                self.assertTrue((evidence[part+'__J'][family]>=0).all())

    def test_malformed_json_not_scientific_missingness(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            path=Path(directory)/'bad.json';path.write_text('{')
            with self.assertRaises(json.JSONDecodeError):adapter.load(path)

    def test_metadata_rejects_bad_time_and_boolean_fps(self):
        legacy=adapter.module_at(run_once.LEGACY,'legacy_metadata_test')
        value=pose_fixture();self.assertEqual(legacy.validate_grid(value)['records'],141)
        value['video']['fps']=True
        with self.assertRaises(ValueError):legacy.validate_grid(value)
        value['video']['fps']=24;value['frames'][70]['time_s']=float('nan')
        with self.assertRaises(ValueError):legacy.validate_grid(value)

    def test_authorization_literal_bool_and_scope(self):
        auth={'authorized':True,'phase':'target','execution_freeze_sha256':'x',
              'candidate_code_freeze_sha256':run_once.CODE_SHA,'candidate_protocol_freeze_sha256':run_once.PROTOCOL_SHA,
              'inputs_sha256':run_once.INPUT_SHA,'allowed_target_ids':['allowed']}
        with patch.object(run_once,'verify_execution',return_value='x'),patch.object(run_once,'read',return_value=auth),patch.object(run_once,'record',return_value={}):
            self.assertEqual(run_once.authorize('allowed'),{})
            with self.assertRaises(ValueError):run_once.authorize('other')
            auth['authorized']=1
            with self.assertRaises(ValueError):run_once.authorize('allowed')

    def test_no_authorization_no_real_phase(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            with patch.object(run_once,'HERE',Path(directory)),patch.object(run_once,'verify_execution',return_value='x'):
                with self.assertRaises(FileNotFoundError):run_once.authorize('anything')

    def test_atomic_commit_refuses_stale_used_file(self):
        legacy=adapter.module_at(run_once.LEGACY,'legacy_commit_test')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            path=Path(directory)/'COMPLETE.json'
            with patch.object(legacy,'require_record',side_effect=ValueError('SHA changed')):
                with self.assertRaises(ValueError):legacy.commit_new(path,{'status':'complete','files':[]},[{'path':'changed'}])
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_finalize_rejects_exchanged_marker_and_input_identity(self):
        target={'id':'target-A','source_id':'source-A','pose':{'path':'A','sha256':'aa','bytes':12}}
        record={'path':'A-result','sha256':'aabb','bytes':24}
        complete={'status':'complete','target_id':'target-A','result':record,'files':[record]}
        result={'target':target.copy(),'source_id':'source-A','input_binding_sha256':'binding'}
        run_once.validate_completed_identity(complete,result,target,'binding')
        other=target|{'id':'target-B'}
        with self.assertRaises(ValueError):
            run_once.validate_completed_identity(complete,result,other,'binding')
        with self.assertRaises(ValueError):
            run_once.validate_completed_identity(complete|{'target_id':'target-B'},result,other,'binding')
        variants=[(complete|{'status':'partial'},result),
                  (complete|{'files':[]},result),
                  (complete,result|{'source_id':'source-B'}),
                  (complete,result|{'target':target|{'pose':{'path':'B','sha256':'bb','bytes':12}}}),
                  (complete,result|{'input_binding_sha256':'old-binding'})]
        for marker,value in variants:
            with self.subTest(marker=marker,value=value):
                with self.assertRaises(ValueError):
                    run_once.validate_completed_identity(marker,value,target,'binding')

    def test_all_methods_preserve_candidate_arrays(self):
        import synthetic_v2
        case=next(c for c in synthetic_v2.cases() if c['id']=='local_single_6')
        a,b,_,_=synthetic_v2.build(case)
        methods,evidence=adapter.analyze_all({h:a for h in adapter.THRESHOLDS},{h:b for h in adapter.THRESHOLDS})
        self.assertEqual(set(methods),{'v1','v2','v3'})
        self.assertEqual(methods['v2']['K'],3);self.assertEqual(methods['v3']['K'],2)
        for key in [k for k in evidence if k.startswith('v2__')]:
            np.testing.assert_equal(evidence[key],evidence['v3__'+key[4:]])
        old=adapter.INPUT_ADAPTER.analyze({h:a for h in adapter.THRESHOLDS},{h:b for h in adapter.THRESHOLDS})[0]
        for key in ('parts','selected','K'):self.assertEqual(old[key],methods['v1'][key])

    def test_method_version_and_safety_schema(self):
        import copy
        method={'parts':{'left_arm':{},'right_arm':{}},'K':0,'selected':[]}
        result={'methods':{name:copy.deepcopy(method) for name in ('v1','v2','v3')},
                'formula':'frozen_v1_v2_v3_side_by_side','unresolved_safety_counterexample':True}
        run_once.validate_method_schema(result)
        with self.assertRaises(ValueError):run_once.validate_method_schema(result|{'methods':{'v3':method}})
        with self.assertRaises(ValueError):run_once.validate_method_schema(result|{'formula':'v1'})
        with self.assertRaises(ValueError):run_once.validate_method_schema(result|{'unresolved_safety_counterexample':1})
        result['methods']['v2']['K']=1
        with self.assertRaises(ValueError):run_once.validate_method_schema(result)

    def test_cold_process_actual_method_order(self):
        import subprocess
        import sys
        code="""import json,sys
import adapter
assert 'frozen' not in sys.modules and 'bindings' not in sys.modules
synth=adapter.module_at(adapter.BASE/'phase_shape_profile_candidate_v1/synthetic.py','cold_synthetic')
a=synth.features('identifiable');b=synth.features('identifiable',6,synth.ROTATION)
methods,evidence=adapter.analyze_all({h:a for h in adapter.THRESHOLDS},{h:b for h in adapter.THRESHOLDS})
assert list(methods)==['v1','v2','v3']
print(json.dumps({name:value['K'] for name,value in methods.items()}))
"""
        process=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertEqual(json.loads(process.stdout),{'v1':2,'v2':2,'v3':2})

    def test_historical_missing_serialization_strict(self):
        import copy
        current={'K':0,'selected':[],'parts':{'left':{'x':float('nan'),'y':float('inf'),'z':1.2345}}}
        historical={'K':0,'selected':[],'parts':{'left':{'x':None,'y':None,'z':1.2345}}}
        run_once.validate_historical_v1(current,historical)
        for mutate in ('finite','extra','nested','count'):
            altered=copy.deepcopy(current)
            if mutate=='finite':altered['parts']['left']['z']+=1e-12
            elif mutate=='extra':altered['parts']['left']['extra']=None
            elif mutate=='nested':altered['parts']['left']['x']=[float('nan')]
            else:altered['K']=1
            with self.assertRaises(ValueError):run_once.validate_historical_v1(altered,historical)


if __name__=='__main__':unittest.main()
