"""CPU contracts: real frozen native execute/tokenizer/layout AST, stub weights.

This does NOT claim real Qwen output equivalence; A0 is the runtime weight gate.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import math
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
import torch.nn.functional as F

STAGE=Path(__file__).resolve().parents[1]
CORE=Path('/Users/researcher/DevProjects/h3-short-event-pilot-20261013/configs/comfy_core_snapshot.tar.gz')
PKG=STAGE/'extensions/H3SemanticClock'
spec=importlib.util.spec_from_file_location('semantic_clock_test_package',PKG/'__init__.py',submodule_search_locations=[str(PKG)])
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

def frozen_source(suffix):
    with tarfile.open(CORE) as tar:
        name=next(n for n in tar.getnames() if n.endswith(suffix))
        return tar.extractfile(name).read().decode()


def extract(source,names,ns):
    nodes=[n for n in ast.parse(source).body if getattr(n,'name',None) in names]
    exec(compile(ast.fix_missing_locations(ast.Module(nodes,type_ignores=[])),'<frozen-actual-AST>','exec'),ns)


def packed_layout():
    ns={'torch':torch,'math':math,'FRAME_PER_TOKEN':(1,4,4,4,4),'FRAME_RESCALE':5/3}
    extract(frozen_source('ldm/minimax/model.py'),{'_axis_from_sqrt_area','_frame_grid','_video_t_spans',
        '_video_t_grid','_ref_t_span','_audio_grid','_video_grid','PackedLayout'},ns)
    return ns['PackedLayout']


class SmallStore:
    def tensor(self,value,save=True):
        return m.tensor_info(value)[0]


class StubClip:
    def __init__(self):
        self.text_segments=[];self.received=None;self.encoded=None
        source=frozen_source('text_encoders/minimax.py')
        cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='MiniMaxH3Tokenizer')
        methods=[n for n in cls.body if getattr(n,'name',None) in ('_vision_entry','tokenize_with_weights')]
        cls.bases=[];cls.keywords=[];cls.body=methods
        ns={'torch':torch,'VISION_START':151652,'VISION_END':151653}
        exec(compile(ast.fix_missing_locations(ast.Module([cls],type_ignores=[])),'<actual-tokenizer>','exec'),ns)
        self.tokenizer=ns['MiniMaxH3Tokenizer']()
        self.tokenizer.qwen3vl_32b=self
    def tokenize_with_weights(self,s,**kwargs):
        self.text_segments.append(s)
        return [[(ord(c),1.) for c in s]]  # Stub vocabulary only; actual block loop is frozen code.
    def tokenize(self,prompt,**kwargs):
        self.received=kwargs
        return self.tokenizer.tokenize_with_weights(prompt,**kwargs)
    def encode_from_tokens_scheduled(self,tokens):
        self.encoded=tokens
        return [[torch.zeros(1,1,2),{}]]


class StubVAE:
    def __init__(self):self.inputs=[]
    def encode(self,frames,*args,**kwargs):
        self.inputs.append(frames.clone())
        return torch.zeros(1,24,1 if len(frames)==1 else 42,4,4)


def native_execute():
    src=frozen_source('comfy_extras/nodes_minimax_h3.py')
    cls=next(n for n in ast.parse(src).body if isinstance(n,ast.ClassDef) and n.name=='MiniMaxH3ReferenceToVideo')
    cls.bases=[];cls.keywords=[];cls.body=[n for n in cls.body if getattr(n,'name',None)=='execute']
    def set_values(cond,values):return [[e,dict(meta,**values)] for e,meta in cond]
    ns={'torch':torch,'math':math,'CANVAS_MULTIPLE':32,'REF_IMAGE_SHORT_EDGE':2048,'FPS':24,
        'adapt_canvas':lambda w,h:(w,h),'_resize':lambda x,w,h,c:x,
        '_empty_av_latent':lambda w,h,n:({'samples':'stub target'},n),
        'node_helpers':types.SimpleNamespace(conditioning_set_values=set_values),
        'io':types.SimpleNamespace(NodeOutput=lambda *args:args)}
    exec(compile(ast.fix_missing_locations(ast.Module([cls],type_ignores=[])),'<actual-native-execute>','exec'),ns)
    return ns['MiniMaxH3ReferenceToVideo'].execute


def exercise(p,t):
    frames=torch.arange(141,dtype=torch.float32)[:,None,None,None].expand(141,64,64,3).clone()/140
    image=torch.zeros(1,64,64,3); vae=StubVAE();store=SmallStore();vp=m.VAEProxy(vae,store)
    clip=StubClip();proxy=m.ClipProxy(clip,vp,store,p,t)
    result=native_execute()(clip=proxy,vae=vp,prompt='fixed prompt',width=64,height=64,length=141,
        ref_image_size='match',ref_images={'ref_image_0':image},ref_videos={'ref_video_0':frames})
    return frames,vae,clip,proxy,result


class ClockTests(unittest.TestCase):
    def test_cpu_only(self):self.assertFalse(torch.cuda.is_available())
    def test_four_clock_plans(self):
        for p,t in ((0,0),(6,6),(0,6),(6,0)):
            plan=m.clock_plan(141,p,t)
            self.assertEqual(plan['sample_indices'],list(range(p,141,12)))
            self.assertEqual(len(plan['sample_indices']),12)
            self.assertEqual(plan['rendered_labels'],['<%.1f seconds>'%(i+.25+t/24) for i in range(6)])
            self.assertEqual(plan['physical_pixel_phase_seconds'],p/24)
    def test_no_padding_or_other_fps(self):
        for args in [(140,0,0),(141,9,0),(141,0,12),(141,True,0)]:
            with self.assertRaises(ValueError):m.clock_plan(*args)
    def test_native_zero_argument_identity(self):
        frames,vae,clip,cp,_=exercise(0,0)
        item=clip.received['minimax_ref_items'][1]
        self.assertTrue(torch.equal(item['data'],frames[::12]))
        self.assertEqual(item['timestamps'],[i/2 for i in range(12)])
        self.assertEqual(len(vae.inputs),2)
        self.assertTrue(torch.equal(vae.inputs[1],frames))
        # Repeat direct proxy with the actual same objects to prove zero fast pass-through.
        items=clip.received['minimax_ref_items']; clip2=StubClip();cp2=m.ClipProxy(clip2,cp.vae,SmallStore())
        cp2.tokenize('fixed prompt',minimax_ref_items=items)
        self.assertIs(clip2.received['minimax_ref_items'],items)
        self.assertIs(clip2.received['minimax_ref_items'][1],items[1])
        self.assertEqual(cp.tokens,cp2.tokens)
    def test_crossed_presentation_and_dense_immutability(self):
        results={}
        for key,p,t in [('A',0,0),('B',6,6),('C',0,6),('D',6,0)]:
            frames,vae,clip,cp,_=exercise(p,t);results[key]=(clip,cp)
            self.assertTrue(torch.equal(vae.inputs[1],frames))
            self.assertTrue(torch.equal(clip.received['minimax_ref_items'][1]['data'],frames[list(range(p,141,12))]))
            self.assertEqual([s for s in clip.text_segments if 'seconds>' in s][-6:],m.clock_plan(141,p,t)['rendered_labels'])
            self.assertEqual(sum(isinstance(e[0],dict) and e[0].get('minimax_video_block',False) for e in clip.encoded['qwen3vl_32b'][0]),6)
        for a,b in [('A','C'),('B','D')]:
            self.assertTrue(torch.equal(results[a][0].received['minimax_ref_items'][1]['data'],results[b][0].received['minimax_ref_items'][1]['data']))
        for a,b in [('A','D'),('B','C')]:
            self.assertEqual(results[a][0].received['minimax_ref_items'][1]['timestamps'],results[b][0].received['minimax_ref_items'][1]['timestamps'])
        self.assertEqual(m.token_structure(results['A'][1].tokens),m.token_structure(results['B'][1].tokens))
    def test_actual_timestamp_spans_and_other_text_ids(self):
        _,_,_,base,_=exercise(0,0)
        for p,t in ((0,0),(6,6),(0,6),(6,0)):
            _,_,_,current,_=exercise(p,t)
            self.assertTrue(m.verify_timestamp_only_text(current.tokens,base.tokens,current.timestamp_lexical_tokens)['non_timestamp_text_ids_equal'])
            bad=copy.deepcopy(current.tokens);bad['qwen3vl_32b'][0][-1][0]+=1
            with self.assertRaises(ValueError):m.verify_timestamp_only_text(bad,base.tokens,current.timestamp_lexical_tokens)

    def test_actual_video_patch_function_sensitivity(self):
        ns={'torch':torch,'math':math,'F':F,'QWEN_IMAGE_MEAN':[.5]*3,'QWEN_IMAGE_STD':[.5]*3}
        extract(frozen_source('text_encoders/minimax.py'),{'process_video_block'},ns)
        allresults={}
        for k,p,t in [('A',0,0),('B',6,6),('C',0,6),('D',6,0)]:
            _,_,clip,_,_=exercise(p,t)
            data=clip.received['minimax_ref_items'][1]['data']
            allresults[k]=ns['process_video_block'](data[:2])[0]
        self.assertTrue(torch.equal(allresults['A'],allresults['C']))
        self.assertTrue(torch.equal(allresults['B'],allresults['D']))
        self.assertFalse(torch.equal(allresults['A'],allresults['B']))
    def test_reject_changed_native_sampler(self):
        frames=torch.zeros(141,2,2,3)
        cp=m.ClipProxy(StubClip(),types.SimpleNamespace(video_frames=frames),SmallStore(),6,6)
        with self.assertRaises(ValueError):cp.tokenize('x',minimax_ref_items=[{'type':'image','data':frames[:1]},
            {'type':'video','data':frames[::12],'timestamps':[i/2+.1 for i in range(12)]}])
    def test_native_full_layout_matches_archived_hash(self):
        base=json.loads((STAGE/'baseline'/m.BASE_CONDITION).read_text())
        refs=[{'kind':'image','latent_h':76,'latent_w':50},
            {'kind':'video','latent_t':42,'latent_h':46,'latent_w':82,'ref_audio_t':0}]
        layout=packed_layout()(base['conditioning_embedding']['shape'][1],42,46,82,235,refs=refs)
        self.assertEqual(m.tensor_info(layout.position_ids)[0],m.identity(base['packed_layout']['position_ids']))
        self.assertEqual(layout.seq_len,base['packed_layout']['seq_len'])
        self.assertTrue(m.verify_against_baseline(base,base,layout,0,0)['zero_embedding_and_tokens_bitwise'])
        for field in ['token_tags','packed_layout','native_vae_calls','conditioning_embedding']:
            bad=copy.deepcopy(base)
            if field=='packed_layout':bad[field]['seq_len']+=1
            elif field=='native_vae_calls':bad[field][1]['latent']['sha256']='bad'
            else:bad[field]['sha256']='bad'
            with self.assertRaises(ValueError):m.verify_against_baseline(bad,base,layout,0,0)
        bad=copy.deepcopy(base);bad['conditioning_embedding']['sha256']='new expected hidden state'
        self.assertTrue(m.verify_against_baseline(bad,base,layout,0,6)['baseline_invariants_passed'])
    def test_path_boundaries_and_stale_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'semantic0';root.mkdir()
            with patch.object(m,'REMOTE_ROOT',root):
                self.assertEqual(m.task_path(root/'audit',mkdir=True),(root/'audit').resolve())
                for p in [root,Path(str(root)+'_bad')/'audit',root/'..'/'escape',Path('relative')]:
                    with self.assertRaises(ValueError):m.task_path(p)
                (root/'outside').symlink_to(Path(d))
                with self.assertRaises(ValueError):m.task_path(root/'outside'/'escape')
                provenance={'x':1};audit=root/'audit'
                with self.assertRaises(FileNotFoundError):m.require_zero_gate(audit,provenance)
                m.atomic_json(audit/(m.ZERO_ID+'_zero_gate.json'),{'passed':True,'provenance':{'x':2}})
                with self.assertRaises(ValueError):m.require_zero_gate(audit,provenance)
                m.atomic_json(audit/(m.ZERO_ID+'_conditioning.json'),{'semantic_clock':{'checks':{'zero_embedding_and_tokens_bitwise':True}}})
                marker={'passed':True,'provenance':provenance,'condition_run_id':m.ZERO_ID,'zero_gate':True,
                        'condition_sha256':m.digest(audit/(m.ZERO_ID+'_conditioning.json'))}
                m.atomic_json(audit/(m.ZERO_ID+'_zero_gate.json'),marker)
                self.assertTrue(m.require_zero_gate(audit,provenance)['passed'])
                (audit/(m.ZERO_ID+'_conditioning.json')).write_text('{}')
                with self.assertRaises(ValueError):m.require_zero_gate(audit,provenance)
    def test_noise_gate_blocks_mismatch_and_zero_gate_checks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()/'semantic0';root.mkdir();audit=root/'audit';audit.mkdir()
            embedding=torch.zeros(1,3,2);positive=[[embedding,{}]]
            streams=[torch.arange(12,dtype=torch.float32).reshape(1,12),torch.ones(1,2)]
            nested=types.SimpleNamespace(is_nested=True,unbind=lambda:streams)
            noise=types.SimpleNamespace(generate_noise=lambda _:nested)
            expected={'actual_noise_streams':[m.tensor_info(x)[0] for x in streams]}
            provenance={'conditioning':'frozen','noise':'frozen','implementation':{'core':'same'}}
            record={'conditioning_embedding':m.tensor_info(embedding)[0],
                'semantic_clock':{'provenance':provenance,'checks':{'baseline_invariants_passed':True,
                                   'zero_embedding_and_tokens_bitwise':True}}}
            m.atomic_json(audit/(m.ZERO_ID+'_conditioning.json'),record)
            with patch.object(m,'REMOTE_ROOT',root),patch.object(m,'read_baselines',return_value=({},expected,provenance)):
                out=m.H3SemanticClockGate().verify(positive,{},noise,str(audit),m.ZERO_ID)
                self.assertIs(out[0],positive)
                self.assertTrue((audit/(m.ZERO_ID+'_zero_gate.json')).exists())
                streams[0].add_(1)
                with self.assertRaises(ValueError):m.H3SemanticClockGate().verify(positive,{},noise,str(audit),m.ZERO_ID)
                self.assertFalse((audit/(m.ZERO_ID+'_zero_gate.json')).exists())
                streams[0].sub_(1)
                record['semantic_clock']['checks']['zero_embedding_and_tokens_bitwise']=False
                m.atomic_json(audit/(m.ZERO_ID+'_conditioning.json'),record)
                with self.assertRaises(ValueError):m.H3SemanticClockGate().verify(positive,{},noise,str(audit),m.ZERO_ID)

    def test_external_state_is_not_cacheable(self):
        self.assertTrue(math.isnan(m.H3SemanticClockReference.IS_CHANGED()))
        self.assertTrue(math.isnan(m.H3SemanticClockGate.IS_CHANGED()))

    def test_pinned_baseline_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();(root/'baseline').mkdir()
            for name in (m.BASE_CONDITION,m.BASE_NOISE):
                (root/'baseline'/name).write_bytes((STAGE/'baseline'/name).read_bytes())
            with patch.object(m,'REMOTE_ROOT',root):
                self.assertEqual(m.read_baselines()[0]['schema'],'h3-event-audit-v1')
                (root/'baseline'/m.BASE_CONDITION).write_text('{}')
                with self.assertRaises(ValueError):m.read_baselines()

    def test_guarded_noise_real_cache_rechecks_marker_and_bytes(self):
        class Nested:
            is_nested=True
            def __init__(self,leaves):self.leaves=leaves
            def unbind(self):return self.leaves
        fixed=[torch.arange(12,dtype=torch.float32).reshape(1,12),torch.ones(1,2)]
        sample=types.ModuleType('comfy.sample'); sample.prepare_noise=lambda *args:Nested([x.clone() for x in fixed])
        nestedmod=types.ModuleType('comfy.nested_tensor'); nestedmod.NestedTensor=Nested
        comfy=types.ModuleType('comfy');comfy.sample=sample;comfy.nested_tensor=nestedmod
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();audit=root/'audit';audit.mkdir()
            expected={'actual_noise_streams':[m.tensor_info(x)[0] for x in fixed]};provenance={'frozen':True}
            manifest={'semantic_clock':{'provenance':provenance,'checks':{'baseline_invariants_passed':True,'zero_embedding_and_tokens_bitwise':True}}}
            m.atomic_json(audit/(m.ZERO_ID+'_conditioning.json'),manifest)
            marker={'passed':True,'provenance':provenance,'condition_run_id':m.ZERO_ID,'zero_gate':True,
                    'condition_sha256':m.digest(audit/(m.ZERO_ID+'_conditioning.json'))}
            markerpath=audit/(m.ZERO_ID+'_zero_gate.json');m.atomic_json(markerpath,marker)
            run='s05_semantic_b_p6_t6';m.atomic_json(audit/(run+'_condition_conditioning.json'),manifest)
            noise=m.GuardedNoise(2026101311,audit,run,'paired')
            target={'samples':Nested([torch.zeros_like(x) for x in fixed])}
            with patch.dict(sys.modules,{'comfy':comfy,'comfy.sample':sample,'comfy.nested_tensor':nestedmod}),patch.object(m,'read_baselines',return_value=({},expected,provenance)):
                out=noise.generate_noise(target)
                self.assertTrue(all(torch.equal(a,b) for a,b in zip(out.unbind(),fixed)))
                self.assertTrue((audit/'paired_noise.pt').exists())
                markerpath.unlink()
                with self.assertRaises(FileNotFoundError):noise.generate_noise(target)
                m.atomic_json(markerpath,dict(marker,passed=False))
                with self.assertRaises(ValueError):noise.generate_noise(target)
                m.atomic_json(markerpath,marker)
                expected['actual_noise_streams'][0]['sha256']='wrong baseline'
                with self.assertRaises(ValueError):noise.generate_noise(target)
                expected['actual_noise_streams'][0]=m.tensor_info(fixed[0])[0]
                cached=torch.load(audit/'paired_noise.pt',weights_only=True)
                cached['tensors'][0].add_(1);torch.save(cached,audit/'paired_noise.pt')
                with self.assertRaises(ValueError):noise.generate_noise(target)

    def test_post_encoding_checker_explicit_guards(self):
        spec=importlib.util.spec_from_file_location('clock_checker',STAGE/'scripts/check_encoded_acceptance.py')
        checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);audit=root/'audit';audit.mkdir();(root/'baseline').mkdir()
            core=root/'extensions/H3SemanticClock';core.mkdir(parents=True)
            for file in PKG.glob('*.py'):(core/file.name).write_bytes(file.read_bytes())
            for name in (m.BASE_CONDITION,m.BASE_NOISE):(root/'baseline'/name).write_bytes((STAGE/'baseline'/name).read_bytes())
            baseline=json.loads((root/'baseline'/m.BASE_CONDITION).read_text())
            noise=json.loads((root/'baseline'/m.BASE_NOISE).read_text())
            provenance={'conditioning':m.digest(root/'baseline'/m.BASE_CONDITION),
                        'noise':m.digest(root/'baseline'/m.BASE_NOISE),'implementation':m.core_digest()}
            baseline['semantic_clock']={'provenance':provenance,'checks':{'reference_target_time_gap':235.,'non_timestamp_text_ids_equal':True}}
            v=next(x for x in baseline['qwen_presentation'] if x['type']=='video');v['sampling']=m.clock_plan(141)
            path=audit/(m.ZERO_ID+'_conditioning.json');m.atomic_json(path,baseline)
            record={'passed':True,'zero_gate':True,'condition_run_id':m.ZERO_ID,'provenance':provenance,
                    'condition_sha256':m.digest(path),'actual_noise_streams':noise['actual_noise_streams']}
            m.atomic_json(audit/(m.ZERO_ID+'_zero_gate.json'),record)
            m.atomic_json(audit/(m.ZERO_ID+'_accepted.json'),record)
            self.assertEqual(len(checker.check(root)['arms']),1)
            with self.assertRaises(ValueError):checker.check(root,require_all=True)
            (core/'__init__.py').write_text('# tampered')
            with self.assertRaises(ValueError):checker.check(root)
        self.assertFalse(any(isinstance(n,ast.Assert) for n in ast.walk(ast.parse((STAGE/'scripts/check_encoded_acceptance.py').read_text()))))

    def test_graphs_scientific_differences(self):
        graphs={n:json.loads((STAGE/'configs'/f's05_semantic_{n}.json').read_text()) for n in ['b_p6_t6','c_p0_t6','d_p6_t0']}
        expected={'b_p6_t6':(6,6),'c_p0_t6':(0,6),'d_p6_t0':(6,0)}
        for n,g in graphs.items():
            self.assertEqual((g['5']['inputs']['pixel_phase_frames'],g['5']['inputs']['label_phase_frames']),expected[n])
            self.assertEqual(g['50']['inputs']['mode'],'native')
            self.assertEqual(g['6']['inputs']['noise_seed'],2026101311)
            self.assertEqual(g['51']['inputs']['positive'],['99',0])
            self.assertEqual(g['51']['inputs']['target'],['99',1])
            self.assertEqual(g['99']['inputs']['noise'],['6',0])
        a=json.loads((STAGE/'configs/s05_semantic_a0_encode_gate.json').read_text())
        self.assertNotIn('SamplerCustomAdvanced',[n['class_type'] for n in a.values()])
        self.assertNotIn('UNETLoader',[n['class_type'] for n in a.values()])
        self.assertEqual(a['99']['class_type'],'H3SemanticClockGate')

if __name__=='__main__':unittest.main(verbosity=2)
