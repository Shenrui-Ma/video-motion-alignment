import hashlib,importlib,json,math,sys,tempfile,types,unittest
from pathlib import Path
from unittest import mock
import torch
from test_correspondence import fixture,dense
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'extensions'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
import r112_contract as contract
from H3TemporalRouter import core,correspondence as c
from H3X0Readout.core import CaptureConfig,PassiveRecorder

class Nested:
    def __init__(self,leaves):self.leaves=leaves
    def unbind(self):return self.leaves

def unpack(value,shapes):
    return [x.reshape(shape) for x,shape in zip(torch.split(value.flatten(),[math.prod(s) for s in shapes]),shapes)]

class DeploymentTests(unittest.TestCase):
    def test_old_cpu_source_verbatim_and_noise_filename(self):
        archive=ROOT/'source_snapshot/cpu_preparation';seal=json.loads((ROOT/'CPU_PREPARATION_SEAL.json').read_text())
        self.assertEqual((archive/'CPU_PREPARATION_SEAL.json').read_bytes(),(ROOT/'CPU_PREPARATION_SEAL.json').read_bytes())
        for rel,row in seal['files'].items():self.assertEqual(hashlib.sha256((archive/rel).read_bytes()).hexdigest(),row['sha256'])
        binding=contract.read(ROOT/'configs/parent_bindings.json')['long_0174']
        for run in contract.registry()[1]:
            graph=contract.read(ROOT/'configs/graphs'/f'{run}.json')
            self.assertEqual(binding['new_noise_relative'],'audit/'+graph['6']['inputs']['pair_id']+'_noise.pt')

    def test_deployment_imports_and_preflight(self):
        import preflight,verify_pair
        self.assertTrue(preflight.check()['passed'])
        self.assertTrue(callable(verify_pair.verify_run));self.assertTrue(callable(verify_pair.verify_pair))
        s=contract.read(ROOT/'configs/scientific_contract.json')['continuous']
        self.assertGreater(s['max_service_seconds'],2*s['job_timeout_seconds'])

    def test_missing_sixth_capture_rejected(self):
        from test_correspondence import prefix
        with tempfile.TemporaryDirectory() as d:
            first=prefix(Path(d)/'first');second=prefix(Path(d)/'second')
            value=json.loads(second.read_text());value['captures']=value['captures'][:5];second.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'six common-prefix'):c.verify_common_prefix(second,first)

    def test_real_recorder_callback_publishes_step5_before_step6_both_arms(self):
        q,k,v,plan,_=fixture();torch.set_num_threads(1)
        original_route=core.route_attention
        def cpu_route(*args,**kwargs):kwargs['attention']=dense;return original_route(*args,**kwargs)
        def attention_pytorch(*args,**kwargs):raise AssertionError('native stub called')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);seen=[];previous=None;previous_bank=None
            for arm in ('fixed_one_bin','matched_one_bin'):
                cfg=CaptureConfig(arm,str(root/'x0'),width=32,height=32,length=5)
                shapes=cfg.shapes
                inner=types.SimpleNamespace(latent_shapes=shapes,audio_scale=lambda:4.,latent_format=types.SimpleNamespace(scale_factor=1.))
                inner.process_latent_out=lambda x:Nested([x.unbind()[0],x.unbind()[1]/4.])
                manifest=root/'x0'/arm/'manifest.json';bankroot=root/'banks'/arm
                config={'root':str(bankroot),'valid_bins':3,'prefix_manifest':str(manifest),'spatial_grid':[1,3]}
                if previous:config.update(paired_prefix_manifest=str(previous),paired_root=str(previous_bank))
                state=core.RouterState({},arm,1.,0,0,0,7,0,50,6,15,arm,str(root/'audit'),num_blocks=50,correspondence_config=config)
                class Executor:
                    class_obj=types.SimpleNamespace(sampler_function=types.SimpleNamespace(__name__='sample_euler'),extra_options={})
                    def __call__(self,model,sigmas,args,callback,noise,*unused):
                        for step in range(20):
                            state.forward_index=step;state.audit['routed_by_forward'].append(0)
                            if step==6:
                                actual=json.loads(manifest.read_text())
                                self_test.assertEqual(actual['callback_count'],6)
                                self_test.assertEqual([x['step_zero_based'] for x in actual['captures']],list(range(6)))
                                self_test.assertEqual(len(state.bank_store.banks),50)
                                seen.append((arm,step,actual['status']))
                            for block in range(50):core.TemporalAttentionOverride(state,plan,block)(attention_pytorch,q,k,v,2,skip_reshape=True,mask=None)
                            state.finish_forward()
                            x0=torch.full_like(noise,float(step));callback(step,x0,x0,20)
                        return x0
                self_test=self
                recorder=PassiveRecorder(cfg,unpack=unpack,nested_factory=Nested)
                noise=torch.zeros(1,1,sum(math.prod(x) for x in shapes))
                with mock.patch.object(core,'route_attention',side_effect=cpu_route):
                    recorder(Executor(),types.SimpleNamespace(inner_model=inner),torch.linspace(1,0,21),{'seed':2026101701},None,noise)
                self.assertTrue(state.audit['correspondence_prefix_gate']['passed'])
                self.assertEqual(state.audit['routed_calls'],450)
                self.assertEqual(len(state.audit['correspondence_bank_captures']),50)
                previous,previous_bank=manifest,bankroot
            self.assertEqual(seen,[('fixed_one_bin',6,'running'),('matched_one_bin',6,'running')])

class LifecycleGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('r112_root_lifecycle',ROOT/'audit/root_run_control.py');cls.life=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.life)
    def make_prior(self,directory):
        root=Path(directory)/'r112';prior=Path(directory)/'r103'
        for p in [root/'configs',prior/'processes',prior/'configs',prior/'audit/attempt']:p.mkdir(parents=True,exist_ok=True)
        identity={'uid':self.life.os.getuid(),'start_ticks':'123','cmdline':str(prior/'scripts/service_entry.py')}
        owner={'pid':1234,'identity':identity,'gpu_uuid':'G','port':8567}
        def save(p,value):p.write_text(json.dumps(value))
        save(prior/'deploy_manifest.json',{'files':{}})
        save(root/'configs/predecessor.json',{'root':str(prior),'producer_seal_sha256':contract.sha(prior/'deploy_manifest.json'),'attempt':'attempt','requires_complete':True})
        save(prior/'configs/runtime.json',{'remote_root':str(prior),'gpu_uuid':'G','port':8567});save(prior/'processes/service.json',owner)
        save(prior/'audit/attempt/COMPLETE.json',{'passed':True,'all_sources_reviewed':True,'GPU_released':True})
        save(prior/'audit/attempt/ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True})
        save(prior/'processes/cleanup.json',{'pid':1234,'process_absent':True,'own_compute_absent':True})
        return root,prior,owner
    def test_predecessor_complete_generation_and_release(self):
        with tempfile.TemporaryDirectory() as d:
            root,prior,owner=self.make_prior(d)
            with mock.patch.object(self.life,'ROOT',root),mock.patch.object(self.life.service,'GPU','G'),mock.patch.object(self.life.service,'current_identity',return_value=None),mock.patch.object(self.life.service,'compute_processes',return_value=[]):
                self.assertEqual(self.life.verify_predecessor()['owner'],owner)
                path=prior/'audit/attempt/COMPLETE.json';value=json.loads(path.read_text());value['all_sources_reviewed']=False;path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'not complete'):self.life.verify_predecessor()
                value['all_sources_reviewed']=True;path.write_text(json.dumps(value))
                with mock.patch.object(self.life.service,'compute_processes',return_value=[{'pid':1234}]):
                    with self.assertRaisesRegex(ValueError,'allocation remains'):self.life.verify_predecessor()
                with mock.patch.object(self.life.service,'current_identity',return_value={'start_ticks':'replacement'}):
                    with self.assertRaisesRegex(ValueError,'still exists'):self.life.verify_predecessor()
    def test_second_arm_needs_first_actual_same_service_gate(self):
        import execution_gate
        order=[contract.run_id(a) for a in contract.ARMS]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'processes').mkdir();folder=root/'analysis/postrun'/order[0];folder.mkdir(parents=True)
            owner={'pid':12,'identity':{'start_ticks':'13'}};(root/'processes/service.json').write_text(json.dumps(owner))
            with mock.patch.object(execution_gate,'registry',return_value=({},order)),mock.patch.object(execution_gate,'approval',return_value={'allowed_runs':order}):
                self.assertTrue(execution_gate.admitted_job(order[0],root))
                with self.assertRaises(FileNotFoundError):execution_gate.admitted_job(order[1],root)
                gate={'passed':True,'checks':{'actual':True},'service_owner':owner,'run_id':order[0]};path=folder/'RUNTIME_GATE.json';path.write_text(json.dumps(gate))
                self.assertTrue(execution_gate.admitted_job(order[1],root))
                gate['service_owner']={'pid':12,'identity':{'start_ticks':'14'}};path.write_text(json.dumps(gate))
                with self.assertRaisesRegex(ValueError,'generation'):execution_gate.admitted_job(order[1],root)
    def test_postrun_recomputes_all50_bank_files_and_rejects_tamper(self):
        import verify_pair
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run='fixture';captures=[];collection={}
            index=torch.arange(943).expand(42,943).clone()
            for block in range(50):
                metadata={'geometry':{'batch':1,'heads':56,'total_bins':47,'valid_bins':43,'frame_rows':943,'head_dim':128},'block':block,'source_step':5,'spatial_grid':[23,41]}
                bank=c.FrozenBank(index,index,metadata);bank.save(root/'audit/correspondence_banks'/run/f'block_{block:02d}')
                collection[str(block)]=bank.manifest['bank_sha256']
                captures.append({'block':block,'bank_sha256':bank.manifest['bank_sha256'],'matching_cuda_synchronized':True,'matching_cuda_seconds':0.125})
            router={'correspondence_bank_captures':captures,'correspondence_bank_collection':{'blocks':collection,'collection_sha256':hashlib.sha256(c.canonical(collection)).hexdigest()}}
            result=verify_pair.verify_banks(root,run,router)
            self.assertEqual(len(result['blocks']),50);self.assertEqual(len(result['files']),100);self.assertEqual(result['total_matching_cuda_seconds'],6.25)
            path=root/'audit/correspondence_banks'/run/'block_49/indices.npz';path.write_bytes(path.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'integrity'):verify_pair.verify_banks(root,run,router)
