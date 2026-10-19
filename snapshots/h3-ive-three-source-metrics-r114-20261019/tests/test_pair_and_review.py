import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import paired
import collect_pair
import render_pair
import review
import collect_decision
from full_frame_review import pages
import test_consumer as fixtures

class PairTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.GateTests();fixture.setUp();self.owner=fixture.owner;self.source=fixture.source
        self.g=copy.deepcopy(fixture.g);self.g['schema']='r114-paired-runtime-gate-v1'
        p=c.info(self.source);r=copy.deepcopy(self.g['runs']['native'])
        r.update(run_id=p['forced_run_id'],routed_blocks=450)
        r['video']['file']=c.config()['producer_remote']+'/output/forced.mp4'
        r['binding_artifacts']={f'configs/graphs/{p["forced_run_id"]}.json':p['forced_graph_sha256'],f'logs/{p["forced_run_id"]}_job.json':r['job_sha256'],f'logs/{p["forced_run_id"]}_history.json':r['history_sha256']}
        self.g['runs']['forced']=r;self.g['checks']=dict.fromkeys(paired.PAIR_CHECKS,True)
        self.g['prefix_tensor_comparison']=[{'step_zero_based':i,'video':True,'audio':True} for i in range(6)]
    def reject(self,change):
        g=copy.deepcopy(self.g);change(g)
        with self.assertRaises(ValueError):paired.verify_pair_gate(g,self.source,self.owner)
    def test_pair_actual_shape(self):paired.verify_pair_gate(self.g,self.source,self.owner)
    def test_each_registered_pair_shape(self):
        for source in c.SOURCES:
            g=copy.deepcopy(self.g);p=c.info(source);g['source_id']=source
            for arm in ('native','forced'):
                r=g['runs'][arm];run=p['run_id'] if arm=='native' else p['forced_run_id'];digest=p['graph_sha256'] if arm=='native' else p['forced_graph_sha256']
                r.update(run_id=run,task_scope=p['task_scope'],evaluation_scope=p['evaluation_scope'],valid_frames=p['valid_frames'])
                r['video']['properties']['nb_read_frames']=str(p['geometry']['frames'])
                r['binding_artifacts']={f'configs/graphs/{run}.json':digest,f'logs/{run}_job.json':r['job_sha256'],f'logs/{run}_history.json':r['history_sha256']}
            paired.verify_pair_gate(g,source,self.owner)
    def test_no_missing_prefix(self):self.reject(lambda g:g.pop('prefix_tensor_comparison'))
    def test_audio_prefix_failure(self):self.reject(lambda g:g['prefix_tensor_comparison'][5].update(audio=False))
    def test_same_output_rejected(self):self.reject(lambda g:g['runs']['forced']['video'].update(file=g['runs']['native']['video']['file']))
    def test_wrong_guidance_calls(self):self.reject(lambda g:g['runs']['forced'].update(routed_blocks=0))
    def test_guided_scope_mismatch(self):self.reject(lambda g:g['runs']['forced'].update(evaluation_scope='IVEBench素材片段探索'))
    def test_wrong_guided_graph(self):self.reject(lambda g:g['runs']['forced']['binding_artifacts'].update({f'configs/graphs/{c.info(self.source)["forced_run_id"]}.json':'f'*64}))
    def test_no_reference_image_input(self):
        for p in c.config()['sources']:
            self.assertFalse(p['reference_image_expected']);self.assertIsNone(p['reference_image'])
    def test_fixed_three_sources(self):self.assertEqual(c.SOURCES,('long_0081','long_0059','long_0163'))
    def test_full_pages_each_length_exact(self):
        for valid in [120,144]:
            result=pages(valid);self.assertEqual([x for row in result for x in row],list(range(valid)))
            self.assertTrue(all(len(x)<=5 for x in result))
    def test_pair_geometry_and_labels(self):
        cmd=render_pair.command(['s','n','f'],'c','o',144,'ffmpeg');f=cmd[cmd.index('-filter_complex')+1]
        self.assertEqual(render_pair.LABELS,('1.参考视频','2.普通编辑','3.时序引导'))
        self.assertEqual(f.count('crop=1280:720:16:8'),3);self.assertEqual(f.count('end_frame=144'),3)
        self.assertNotIn('fps=',f);self.assertNotIn('minterpolate',f)
    def test_skip_never_yields_pair(self):
        with patch.object(collect_pair,'ROOT',Path('/fixture/no-pair-output')),patch.object(collect_pair,'status',return_value={'status':'PENDING_GATE'}),patch.object(collect_pair,'fetch') as fetch:
            with self.assertRaises(ValueError):collect_pair.collect(self.source)
            fetch.assert_not_called()
    def decision(self,choice):
        g=copy.deepcopy(self.g);g['schema']='r114-native-runtime-gate-v1';g['runs'].pop('forced')
        return {'schema':'r114-root-native-decision-v1','root_reviewed':True,'choice':choice,'reason':'test',
            'binding':{'source_id':self.source,'native_run':c.info(self.source)['run_id'],'native_gate_sha256':'a'*64,
            'runtime_profile_sha256':c.config()['producer_runtime_sha256'],'service_owner':g['service_owner'],
            'video_sha256':g['runs']['native']['video']['sha256']}},g
    def test_actual_skip_and_guide_binding(self):
        for choice in ('skip','guide'):
            decision,gate=self.decision(choice);collect_decision.validate_decision(decision,self.source,gate,'a'*64)
    def test_actual_decision_wrong_native_rejected(self):
        decision,gate=self.decision('guide');decision['binding']['video_sha256']='f'*64
        with self.assertRaises(ValueError):collect_decision.validate_decision(decision,self.source,gate,'a'*64)
    def test_actual_decision_requires_root_review(self):
        decision,gate=self.decision('skip');decision['root_reviewed']=False
        with self.assertRaises(ValueError):collect_decision.validate_decision(decision,self.source,gate,'a'*64)

class ReviewTests(unittest.TestCase):
    def fixture(self,source='long_0081',paired_mode=True):
        arms=('native','forced') if paired_mode else ('native',)
        events=[]
        for cue in review.mapped_cues(source):
            events.append({**cue,**{arm:{'status':'OBSERVED','frames':[10,12],'notes':''} for arm in ('source',)+arms}})
        return {'source_id':source,'mode':'paired' if paired_mode else 'native','all_valid_frames_inspected':True,
            'examined_frames':list(range(c.info(source)['valid_frames'])),'reviewer':'SYNTHETIC UNIT TEST',
            'task_acceptance':{arm:{'status':'PASS',**dict.fromkeys(review.COMPONENTS,'PASS')} for arm in arms},
            'whole_clip_quality':{arm:{'status':'ACCEPTABLE'} for arm in arms},'events':events,
            'guide_or_skip_recommendation':None if paired_mode else {'choice':'guide','reason':'synthetic test'}}
    def test_paired_eligible(self):self.assertTrue(all(x['primary_timing_comparison_eligible'] for x in review.validate_completed(self.fixture())['events']))
    def test_task_failed_scores_kept_separate(self):
        x=self.fixture();x['task_acceptance']['native']['status']='FAIL';r=review.validate_completed(x)
        self.assertIsNone(r['events'][0]['paired_comparison']);self.assertIsNotNone(r['events'][0]['observed_delays']['native'])
    def test_false_task_pass_rejected(self):
        x=self.fixture();x['task_acceptance']['native']['requested_edit']='FAIL'
        with self.assertRaises(ValueError):review.validate_completed(x)
    def test_unknown_event_no_numeric_score(self):
        x=self.fixture();x['events'][0]['forced']={'status':'UNKNOWN','frames':None,'notes':'occluded'}
        self.assertIsNone(review.validate_completed(x)['events'][0]['paired_comparison'])
    def test_unknown_event_requires_reason(self):
        x=self.fixture();x['events'][0]['forced']={'status':'UNKNOWN','frames':None,'notes':''}
        with self.assertRaises(ValueError):review.validate_completed(x)
    def test_padding_frames_rejected(self):
        for source in c.SOURCES:
            x=self.fixture(source);x['events'][0]['native']['frames']=[c.info(source)['valid_frames']]*2
            with self.assertRaises(ValueError):review.validate_completed(x)
    def test_missing_full_frame_rejected(self):
        x=self.fixture();x['examined_frames'].pop()
        with self.assertRaises(ValueError):review.validate_completed(x)
    def test_cues_never_retimed_arbitrarily(self):
        for source in c.SOURCES:
            p=c.info(source);mapping=c.read(c.ROOT/p['provenance']['file'])['input_to_original_frame'][:p['valid_frames']]
            for cue in review.mapped_cues(source):
                self.assertEqual(cue['prepared_frame_cue'],[i for i,x in enumerate(mapping) if cue['original_frame_cue'][0]<=x<=cue['original_frame_cue'][1]])
    def test_native_guide_and_skip_both_valid(self):
        for choice in ('guide','skip'):
            x=self.fixture(paired_mode=False);x['guide_or_skip_recommendation']['choice']=choice
            self.assertEqual(review.validate_completed(x)['guide_or_skip_recommendation']['choice'],choice)
    def test_pending_not_complete(self):
        x=self.fixture(paired_mode=False);x['guide_or_skip_recommendation']['choice']='PENDING'
        with self.assertRaises(ValueError):review.validate_completed(x)

if __name__=='__main__':unittest.main()
