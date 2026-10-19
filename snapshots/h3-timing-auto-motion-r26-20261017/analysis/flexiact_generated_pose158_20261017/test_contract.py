import copy
import importlib.util
import sys
import tempfile
import types
import unittest
from contract import HERE, read, sha, save, expected_run, validate_metadata, validate_paths, source_helper
from manifest import verified_record, verify_complete_identity, compare_supplied_record


def fixture(protocol, source='chest', method='native'):
    item = protocol['pairs'][source]
    root = protocol['methods'][method]['root_remote']
    run = expected_run(protocol, source, method)
    folder = root + '/analysis/postrun/captured/batch/final/' + run
    metric = {'source_id': source, 'official_pair_id': item['pair_id'], 'run_id': run, 'original_source':root+'/inputs/original.mp4', 'target_image':root+'/inputs/portrait.webp', 'original_source_sha256': item['original_source_sha256'], 'target_sha256': item['target_sha256'], 'source_frames': 49, 'output_frames': 49, 'source_fps': 8, 'output_fps': 8, 'source_size': [720, 480], 'output_size': [1152, 768], 'source_indices': list(range(49)), 'full_output_indices': list(range(0, 147, 3)), 'physical_seconds': [i/8 for i in range(49)], 'padding_evaluated': False, 'score_computed': False, 'full158_output': root + '/output/' + run + '.mp4', 'full158_output_sha256': 'full', 'edited49': folder + '/edited49_8fps.mp4', 'edited49_sha256': 'release'}
    mapping = {'input_indices': list(range(0,147,3)), 'physical_seconds': [i/8 for i in range(49)], 'terminal_padding_excluded': True, 'decoded_frame_md5_equal': True, 'source': metric['full158_output'], 'source_sha256': 'full', 'destination': metric['edited49'], 'destination_sha256': 'release'}
    return metric, mapping


class Contracts(unittest.TestCase):
    def setUp(self):
        self.p = read(HERE / 'PROTOCOL.json')
        self.m, self.r = fixture(self.p)

    def check(self):
        validate_metadata(self.p, 'chest', 'native', self.m, self.r)

    def test_all_ten(self):
        for source in self.p['source_order']:
            for method in self.p['methods']:
                m,r = fixture(self.p,source,method)
                validate_metadata(self.p,source,method,m,r)

    def test_wrong_pair(self):
        self.m['official_pair_id']='human/crouch/000'
        with self.assertRaises(ValueError): self.check()

    def test_wrong_method(self):
        self.m['run_id']=expected_run(self.p,'chest','automatic')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_target(self):
        self.m['target_sha256']='other'
        with self.assertRaises(ValueError): self.check()

    def test_no_repeat_weighting(self):
        self.m['full_output_indices']=list(range(49))
        with self.assertRaises(ValueError): self.check()

    def test_missing_last_sample(self):
        self.r['input_indices']=self.r['input_indices'][:-1]
        with self.assertRaises(ValueError): self.check()

    def test_padding_rejected(self):
        self.m['padding_evaluated']=True
        with self.assertRaises(ValueError): self.check()

    def test_nonliteral_boolean(self):
        self.r['decoded_frame_md5_equal']=1
        with self.assertRaises(ValueError): self.check()

    def test_nonfinite_time(self):
        self.m['physical_seconds'][20]=float('nan')
        with self.assertRaises(ValueError): self.check()

    def test_shifted_time(self):
        self.m['physical_seconds'][20]+=.01
        with self.assertRaises(ValueError): self.check()

    def test_full_output_hash_mismatch(self):
        self.r['source_sha256']='other'
        with self.assertRaises(ValueError): self.check()

    def test_release_output_hash_mismatch(self):
        self.r['destination_sha256']='other'
        with self.assertRaises(ValueError): self.check()

    def test_wrong_method_path(self):
        self.m['full158_output']=self.p['methods']['automatic']['root_remote']+'/output/a.mp4'
        folder=self.p['methods']['native']['root_remote']+'/analysis/postrun/x'
        with self.assertRaises(ValueError): validate_paths(self.p,'native',folder+'/METRIC_INPUTS.json',self.m['edited49'].replace('.mp4','.mapping.json'),self.m)

    def test_swapped_complete(self):
        marker={'status':'complete','source_id':'crouch','method':'native','pair_id':'human/crouch/000','code_freeze_sha256':'seal'}
        with self.assertRaises(ValueError): verify_complete_identity(marker,'chest','native','human/chest/000','seal')

    def test_old_code_complete(self):
        marker={'status':'complete','source_id':'chest','method':'native','pair_id':'human/chest/000','code_freeze_sha256':'oldseal'}
        with self.assertRaises(ValueError): verify_complete_identity(marker,'chest','native','human/chest/000','seal')

    def test_pending_has_no_invented_paths(self):
        item=verified_record(self.p,'chest','native')
        self.assertEqual(item['status'],'pending')
        self.assertIsNone(item['pose_path']);self.assertIsNone(item['full158_sha256'])

    def test_frozen_pose_helper(self):
        self.assertTrue(callable(source_helper(self.p).validate_pose))

    def test_import_ignores_other_contract(self):
        old = sys.modules.get('contract')
        sys.modules['contract'] = types.ModuleType('contract')
        try:
            spec = importlib.util.spec_from_file_location('isolated_receipt_test', HERE / 'manifest.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.HERE,HERE)
            self.assertTrue(callable(module.verify_supplied_record))
        finally:
            if old is None: sys.modules.pop('contract',None)
            else: sys.modules['contract']=old

    def test_local_copy_locations_can_differ(self):
        a={'status':'complete','pose_sha256':'p','local_paths':{'pose':'/Users/a'}}
        b={'status':'complete','pose_sha256':'p','local_paths':{'pose':'/data5/a'}}
        self.assertIs(compare_supplied_record(a,b),b)

    def test_supplied_scientific_or_identity_diff_rejected(self):
        a={'status':'complete','pose_sha256':'p','original_sample_indices':[0,3,6]}
        b=dict(a,original_sample_indices=[0,1,2])
        with self.assertRaises(ValueError): compare_supplied_record(a,b)

    def test_supplied_extra_field_rejected(self):
        a={'status':'complete','pose_sha256':'p'}
        b=dict(a,full158_sha256='other')
        with self.assertRaises(ValueError): compare_supplied_record(a,b)

    def test_pending_cannot_be_scored(self):
        with self.assertRaises(ValueError): compare_supplied_record({'status':'pending'},{'status':'pending'})

    def test_full_synthetic_receipt_and_swapped_marker(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('manifest.py','contract.py','PROTOCOL.json'):
                (root/name).write_bytes((HERE/name).read_bytes())
            save(root/'FREEZE.json',{'files':{n:sha(root/n) for n in ('manifest.py','contract.py','PROTOCOL.json')}})
            spec=importlib.util.spec_from_file_location('toy_complete_receipt',root/'manifest.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            folder=root/'records/native_chest';folder.mkdir(parents=True)
            m,r=self.m,self.r
            save(folder/'METRIC_INPUTS.json',m);save(folder/'release49.mapping.json',r)
            mp=str(Path(m['edited49']).parent/'METRIC_INPUTS.json');rp=str(Path(m['edited49']).with_suffix('.mapping.json'))
            save(folder/'PARENT_CASE_FILES.json',{'METRIC_INPUTS.json':sha(folder/'METRIC_INPUTS.json'),'edited49_8fps.mapping.json':sha(folder/'release49.mapping.json')})
            inputs={mp:sha(folder/'METRIC_INPUTS.json'),rp:sha(folder/'release49.mapping.json'),str(Path(mp).parent/'CASE_FILES.json'):sha(folder/'PARENT_CASE_FILES.json'),m['full158_output']:m['full158_output_sha256'],m['edited49']:m['edited49_sha256'],m['original_source']:m['original_source_sha256'],m['target_image']:m['target_sha256']}
            bind={'pair_id':m['official_pair_id'],'source_id':'chest','method':'native','run_id':m['run_id'],'metric_inputs_path':mp,'release49_mapping_path':rp,'actual_inputs':inputs,'full158_path':m['full158_output'],'full158_sha256':m['full158_output_sha256'],'code_freeze_sha256':sha(root/'FREEZE.json')}
            save(folder/'INPUT_BINDING.json',bind)
            ep=self.p['frozen_external']
            prov={'device':'cpu','providers':['CPUExecutionProvider'],'threads':4}
            for key,suffix in [('script_sha256','/pose_probe.py'),('detector_sha256','/yolox_l.onnx'),('pose_sha256','/dw-ll_ucoco_384_bs5.torchscript.pt'),('detector_code_sha256','/cv_ox_det.py'),('pose_code_sha256','/jit_pose.py')]: prov[key]=next(v for k,v in ep.items() if k.endswith(suffix))
            pose=folder/'toy.pose.json'
            raw={'video':{'sha256':'full','container_frame_count':158,'fps':24,'width':1152,'height':768},'frames':[{'frame':i,'time_s':i/24} for i in range(158)],'extraction':self.p['extraction'],'provenance':prov,'statistics':{'processed_frames':158}}
            save(pose,raw)
            save(folder/'PROVENANCE.json',{'pair_id':bind['pair_id'],'source_id':'chest','method':'native','pose_path':self.p['root_remote']+'/records/native_chest/toy.pose.json','pose_sha256':sha(pose),'raw_provenance':prov,'statistics':raw['statistics'],'input_binding_sha256':sha(folder/'INPUT_BINDING.json'),'code_freeze_sha256':sha(root/'FREEZE.json'),'protocol_sha256':sha(root/'PROTOCOL.json'),'elapsed_seconds':1.0})
            complete={'status':'complete','pair_id':bind['pair_id'],'source_id':'chest','method':'native','code_freeze_sha256':sha(root/'FREEZE.json'),'files':{f.name:sha(f) for f in folder.iterdir()}}
            save(folder/'COMPLETE.json',complete)
            record=module.verified_record(self.p,'chest','native')
            self.assertEqual(module.verify_supplied_record(record)['status'],'complete')
            complete['source_id']='crouch';save(folder/'COMPLETE.json',complete)
            with self.assertRaises(ValueError): module.verify_supplied_record(record)


if __name__=='__main__': unittest.main()
