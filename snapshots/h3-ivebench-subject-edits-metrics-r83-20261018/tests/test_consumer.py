import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import common as c
import collect_pair as collect
import bindings as b
import prepare_pair as prepare
import watch_actual_pairs as watcher
import make_showcase as show

def gate(source):
    p=c.entry(source)['input_protocol']
    return {'schema':'r83-paired-runtime-gate-v1','passed':True,'source_id':source,'prompt_version':'P1-local-v1',
      'checks':{k:True for k in ('producer_seal','actual_runtime_device','actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal')},
      'runs':{m:{'run_id':c.run_id(source,m),'valid_frames':p['effective_frame_count'],'NFE':20,'Euler_updates':20,'routed_blocks':0 if m=='native' else 450,'evaluation_crop_xywh':[16,8,1280,720],
       'video':{'properties':{'width':1312,'height':736,'nb_read_frames':str(p['h3_frame_count']),'avg_frame_rate':'24/1'}}} for m in c.METHODS}}
class Binding(unittest.TestCase):
    def test_seven_durations(self):
        self.assertEqual([(c.entry(s)['input_protocol']['h3_frame_count'],c.entry(s)['input_protocol']['effective_frame_count']) for s in c.PAIRS],[(56,43),(107,97),(73,61),(73,72),(73,66),(107,105),(124,121)])
    def test_all_gate_shapes(self):
        for s in c.PAIRS:self.assertTrue(collect.validate_gate(gate(s),s)['passed'])
    def test_failed_or_missing_prefix(self):
        for mode in ('false','missing'):
            g=gate(c.PAIRS[0])
            if mode=='false':g['checks']['Native_prefix_0_5_equal']=False
            else:del g['checks']['Native_prefix_0_5_equal']
            with self.assertRaises(ValueError):collect.validate_gate(g,c.PAIRS[0])
    def test_each_count_and_time_field(self):
        g0=gate(c.PAIRS[0])
        for field,value in [('NFE',29),('Euler_updates',19),('routed_blocks',0),('valid_frames',56)]:
            g=copy.deepcopy(g0);g['runs']['forced'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):collect.validate_gate(g,c.PAIRS[0])
        for field,value in [('width',1280),('height',720),('nb_read_frames','90'),('avg_frame_rate','8/1')]:
            g=copy.deepcopy(g0);g['runs']['forced']['video']['properties'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):collect.validate_gate(g,c.PAIRS[0])
    def test_wrong_protocol_or_source(self):
        for field,value in [('schema','r73-paired-runtime-gate-v1'),('prompt_version','P1'),('source_id','short_0230')]:
            g=gate(c.PAIRS[0]);g[field]=value
            with self.assertRaises(ValueError):collect.validate_gate(g,c.PAIRS[0])
    def test_real_source_and_prompt_binding(self):
        contract=c.read(ROOT/'configs/producer_scientific_contract.json')
        for s in c.PAIRS:
            native,forced=[x for x in contract['cases'] if x['source_id']==s]
            self.assertEqual(native['prompt'],forced['prompt'])
            self.assertEqual(native['prompt'],(ROOT/'configs/prompts'/f'{s}.txt').read_text())
            graph={'5':{'inputs':{'prompt':native['prompt'],'length':native['geometry']['frames']}}}
            prepare.validate_generation_graph(graph,s)
            graph['5']['inputs']['prompt']+=' changed'
            with self.assertRaises(ValueError):prepare.validate_generation_graph(graph,s)
    def test_media_pts_rejected(self):
        info={'width':1312,'height':736,'count':56,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(56)]};b.validate_full(info,56)
        info['pts_s'][4]+=.001
        with self.assertRaises(ValueError):b.validate_full(info,56)
    def test_inherited_numerics(self):c.verify_runtime(inputs=False)
    def test_start_requires_actual_matching_service(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'audit/attempt').mkdir(parents=True);(p/'processes').mkdir();(p/'configs').mkdir()
            owner={'pid':1,'identity':{'uid':3,'start_ticks':7,'cmdline_sha256':'a'},'gpu_uuid':'GPU-abc','port':8549}
            c.save(p/'processes/service.json',owner);c.save(p/'configs/runtime.json',{'gpu_uuid':'GPU-abc','port':8549})
            receipt=p/'audit/attempt/STARTED.json';c.save(receipt,{'owner':owner,'controller':{'pid':2}})
            self.assertEqual(watcher.started_receipt(p,receipt)['sha256'],c.sha(receipt))
            owner['pid']=2;c.replace(p/'processes/service.json',owner)
            with self.assertRaises(ValueError):watcher.started_receipt(p,receipt)
    def test_failures_are_explicit_and_other_sources_pending(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'logs').mkdir();s=c.PAIRS[0]
            c.save(p/'logs'/(c.run_id(s,'native')+'_job.json'),{'status':'error'})
            self.assertEqual(watcher.generation_status(p,s)['generation'],'GENERATION_FAILED')
            self.assertEqual(watcher.generation_status(p,c.PAIRS[1])['generation'],'RUNNING_OR_PENDING')
    def test_unknown_observation_is_pending_then_success_can_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'logs').mkdir();s=c.PAIRS[0]
            for m in c.METHODS:c.save(p/'logs'/(c.run_id(s,m)+'_job.json'),{'status':'unknown_missing'})
            self.assertEqual(watcher.generation_status(p,s)['generation'],'RUNNING_OR_PENDING')
            for m in c.METHODS:c.replace(p/'logs'/(c.run_id(s,m)+'_job.json'),{'status':'success'})
            self.assertEqual(watcher.generation_status(p,s)['generation'],'COMPLETE')
    def test_fixed_denominator_in_pending_html(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'index.html';show.build(output)
            result=c.read(output.with_suffix('.json'));self.assertEqual(len(result['rows']),7);self.assertEqual(result['fixed_denominator'],7)
            self.assertTrue(all(s in output.read_text() for s in c.PAIRS))
    def test_caption_is_below_panels(self):
        from render_pair import caption_strip,choose_font
        image=caption_strip(choose_font());self.assertEqual(image.size,(3840,88))
if __name__=='__main__':unittest.main()
