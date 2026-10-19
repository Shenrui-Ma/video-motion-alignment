import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import render_native as r
import collect_native as intake

class GateTests(unittest.TestCase):
 def setUp(self):
  self.source='long_0047';p=c.info(self.source);conf=c.config();self.owner={'pid':123,'identity':{'uid':1016,'start_ticks':'42','cmdline':'exact'},'gpu_uuid':'g','port':1}
  run=p['run_id'];self.g={'schema':'r92-native-runtime-gate-v1','passed':True,'source_id':self.source,'prompt_version':p['prompt_version'],'runs':{'native':{'run_id':run,'NFE':20,'Euler_updates':20,'routed_blocks':0,'valid_frames':p['valid_frames'],'evaluation_crop_xywh':p['crop_xywh'],'video':{'file':conf['producer_remote']+'/output/native.mp4','sha256':'a'*64,'properties':{'width':1312,'height':736,'nb_read_frames':str(p['geometry']['frames']),'avg_frame_rate':'24/1'}},'job_sha256':'b'*64,'history_sha256':'c'*64,'binding_artifacts':{f'configs/graphs/{run}.json':p['graph_sha256'],f'logs/{run}_job.json':'b'*64,f'logs/{run}_history.json':'c'*64}}},'checks':dict.fromkeys(c.REQUIRED_CHECKS,True),'runtime_profile_sha256':conf['producer_runtime_sha256'],'runtime_profile':c.read(c.ROOT/'configs/producer_runtime.json'),'service_owner':{'pid':123,'identity':self.owner['identity']}}
 def reject(self,edit):
  g=copy.deepcopy(self.g);edit(g)
  with self.assertRaises(ValueError):c.verify_gate(g,self.source,self.owner)
 def test_actual_native_schema(self):self.assertIs(c.verify_gate(self.g,self.source,self.owner),self.g)
 def test_no_pair_substitution(self):self.reject(lambda g:g.update(schema='r92-paired-runtime-gate-v1'))
 def test_no_third_column(self):self.reject(lambda g:g['runs'].update(forced=g['runs']['native']))
 def test_failed_gate(self):self.reject(lambda g:g.update(passed=False))
 def test_missing_required_check(self):self.reject(lambda g:g['checks'].pop('native_actual_noise_cache'))
 def test_false_check(self):self.reject(lambda g:g['checks'].update(native_history=False))
 def test_new_unknown_failure_check(self):self.reject(lambda g:g['checks'].update(extra=False))
 def test_generation_changed(self):self.reject(lambda g:g['service_owner']['identity'].update(start_ticks='43'))
 def test_runtime_changed(self):self.reject(lambda g:g.update(runtime_profile_sha256='0'*64))
 def test_wrong_source(self):self.reject(lambda g:g.update(source_id='long_0123'))
 def test_wrong_prompt(self):self.reject(lambda g:g.update(prompt_version='P0'))
 def test_guidance_claim_rejected(self):self.reject(lambda g:g['runs']['native'].update(routed_blocks=450))
 def test_wrong_valid_domain(self):self.reject(lambda g:g['runs']['native'].update(valid_frames=107))
 def test_wrong_geometry(self):self.reject(lambda g:g['runs']['native']['video']['properties'].update(nb_read_frames='106'))
 def test_wrong_graph(self):self.reject(lambda g:g['runs']['native']['binding_artifacts'].update({f'configs/graphs/{c.info(self.source)["run_id"]}.json':'0'*64}))
 def test_unsafe_video(self):self.reject(lambda g:g['runs']['native']['video'].update(file=c.config()['producer_remote']+'/output/../logs/x'))
 def test_unsafe_binding(self):self.reject(lambda g:g['runs']['native']['binding_artifacts'].update({'../parent.json':'d'*64}))
 def test_pending_is_not_success(self):
  cfg=c.config();binding={'owner':self.owner};root=Path(cfg['producer_remote']);gate=str(root/'analysis/postrun'/self.source/'NATIVE_RUNTIME_GATE.json')
  data={str(root/'deploy_manifest.json'):{'sha256':cfg['producer_seal_sha256']},str(root/'configs/runtime.json'):{'sha256':cfg['producer_runtime_sha256']},str(root/'processes/service.json'):{'value':self.owner},gate:None,str(Path(gate).with_name('NATIVE_RUNTIME_GATE_FAILURE.json')):None}
  with patch.object(intake,'validate_static',return_value=cfg),patch.object(intake,'read',return_value=binding),patch.object(intake,'read_paths',return_value=data):self.assertEqual(intake.status(self.source)['status'],'PENDING_GATE')
 def test_pending_does_not_fetch(self):
  with patch.object(intake,'ROOT',Path('/does-not-exist-fixture')),patch.object(intake,'status',return_value={'status':'PENDING_GATE'}),patch.object(intake,'fetch') as fetch:
   with self.assertRaises(ValueError):intake.collect(self.source)
   fetch.assert_not_called()

class TimeTests(unittest.TestCase):
 def test_fixed_five_denominator(self):self.assertEqual(c.config()['source_order'],list(c.SOURCES));self.assertEqual(len(c.SOURCES),5)
 def test_samples_keep_original_indices(self):self.assertEqual(r.frame_indices(97,6),[0,19,38,58,77,96]);self.assertEqual(r.frame_indices(145,12)[-1],144)
 def test_nonuniform_pts_rejected(self):
  s={'width':1312,'height':736,'count':3,'avg_frame_rate':'24/1','pts_s':[0,1/24,3/24]}
  with self.assertRaises(ValueError):r.check_time(s,3,1312,736)
 def test_framecount_rejected(self):
  s={'width':1312,'height':736,'count':2,'avg_frame_rate':'24/1','pts_s':[0,1/24]}
  with self.assertRaises(ValueError):r.check_time(s,3,1312,736)
 def test_command_has_only_two_columns_no_timewarp(self):
  cmd=r.command(['source','native'],'caption','out',97,'ffmpeg');f=cmd[cmd.index('-filter_complex')+1]
  self.assertIn('hstack=inputs=2',f);self.assertNotIn('hstack=inputs=3',f);self.assertIn('end_frame=97',f);self.assertNotIn('minterpolate',f);self.assertNotIn('fps=',f)
 def test_extra_input_rejected(self):
  with self.assertRaises(ValueError):r.command(['source','native','forced'],'c','o',97,'ffmpeg')
 def test_native_labels(self):self.assertEqual(r.LABELS,('1.参考视频','2.普通编辑'))


class EvidenceTests(unittest.TestCase):
 def test_actual_job_history_and_output_hash(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d);source='long_0047';p=copy.deepcopy(c.info(source));owner={'pid':123,'identity':{'uid':1016,'start_ticks':'42','cmdline':'exact'}};graph={'5':{'class_type':'Text','inputs':{'prompt':'SYNTHETIC TEST ONLY'}}};(path/'native_graph.json').write_text(json.dumps(graph));p['graph_sha256']=c.sha(path/'native_graph.json');(path/'native.mp4').write_bytes(b'SYNTHETIC NONMEDIA EVIDENCE FIXTURE')
   job={'status':'success','name':p['run_id'],'service_pid':123,'service_identity':owner['identity'],'graph_sha256':p['graph_sha256'],'prompt_id':'fixture-prompt'}
   history={'status':{'completed':True,'status_str':'success'},'prompt':[0,'fixture-prompt',graph],'outputs':{'14':{'images':[{'filename':'test.mp4','subfolder':'','type':'output'}]}}};g={'runs':{'native':{'video':{'file':c.config()['producer_remote']+'/output/test.mp4','sha256':c.sha(path/'native.mp4')}}}}
   (path/'native_job.json').write_text(json.dumps(job));(path/'native_history.json').write_text(json.dumps(history))
   with patch.object(c,'info',return_value=p):
    c.verify_small_evidence(path,source,owner,g)
    # PID reuse with changed start generation is a hard rejection.
    job['service_identity']={**owner['identity'],'start_ticks':'43'};(path/'native_job.json').write_text(json.dumps(job))
    with self.assertRaises(ValueError):c.verify_small_evidence(path,source,owner,g)
    job['service_identity']=owner['identity'];(path/'native_job.json').write_text(json.dumps(job));history['prompt'][1]='wrong';(path/'native_history.json').write_text(json.dumps(history))
    with self.assertRaises(ValueError):c.verify_small_evidence(path,source,owner,g)
    history['prompt'][1]='fixture-prompt';(path/'native_history.json').write_text(json.dumps(history));(path/'native.mp4').write_bytes(b'changed')
    with self.assertRaises(ValueError):c.verify_small_evidence(path,source,owner,g)

if __name__=='__main__':unittest.main()
