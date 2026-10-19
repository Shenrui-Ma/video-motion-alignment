"""Synthetic CPU fixtures test contract handling, not generated-video quality."""
import copy,sys,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import render_pair as r
import make_showcase as show
import remote
import collect_pair
import bind_execution
import consume_pair
import verify_showcase
class ConsumerTests(unittest.TestCase):
 def gate(self,pair=c.PAIRS[0]):
  p=c.pair_info(pair);checks={k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','actual_runtime_device','native_service','forced_service','native_actual_layout','forced_actual_layout','native_actual_execution_counts','forced_actual_execution_counts']}
  g={'schema':'r91-paired-runtime-gate-v1','passed':True,'source_id':pair,'prompt_version':p['prompt_version'],'checks':checks,'runtime_profile_sha256':c.config()['producer_runtime_sha256'],'runs':{}}
  for arm in c.METHODS:g['runs'][arm]={'run_id':p['runs'][arm]['run_id'],'valid_frames':p['valid_frames'],'NFE':20,'Euler_updates':20,'routed_blocks':0 if arm=='native' else 450,'evaluation_crop_xywh':p['evaluation_crop_xywh'],'video':{'properties':{'width':1312,'height':736,'nb_read_frames':str(p['geometry']['frames']),'avg_frame_rate':'24/1'}}}
  return g
 def test_two_actual_shapes(self):
  for pair in c.PAIRS:self.assertIs(c.verify_gate(g:=self.gate(pair),pair),g)
  self.assertEqual([c.pair_info(x)['valid_frames'] for x in c.PAIRS],[105,144])
  self.assertEqual([c.pair_info(x)['geometry']['frames'] for x in c.PAIRS],[107,158])
 def test_failed_gate_rejected(self):
  g=self.gate();g['passed']=False
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_missing_prefix_rejected(self):
  g=self.gate();del g['checks']['Native_prefix_0_5_equal']
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_nonboolean_check_rejected(self):
  g=self.gate();g['checks']['producer_seal']=1
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_prompt_version_rejected(self):
  g=self.gate();g['prompt_version']='P1'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_pair_rejected(self):
  with self.assertRaises(ValueError):c.verify_gate(self.gate(),c.PAIRS[1])
 def test_old_host41_output_rejected(self):
  g=self.gate();g['runs']['native']['run_id']='r83_short_0131_seed2026101701_native'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_all_off_forced_rejected(self):
  g=self.gate();g['runs']['forced']['routed_blocks']=0
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_tailpad_not_valid(self):
  g=self.gate();g['runs']['forced']['valid_frames']=56
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_padding_crop(self):
  g=self.gate();g['runs']['native']['evaluation_crop_xywh']=[0,0,1280,720]
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_actual_geometry(self):
  g=self.gate();g['runs']['native']['video']['properties']['nb_read_frames']='158'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_runtime_rejected(self):
  g=self.gate();g['runtime_profile_sha256']='old41'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_output_path_bounds(self):
  root=c.config()['producer_remote'];self.assertEqual(str(c.safe_output(root+'/output/a.mp4')),root+'/output/a.mp4')
  for p in [root+'/other/a.mp4',root+'/output/../a.mp4','/tmp/a.mp4']:
   with self.assertRaises(ValueError):c.safe_output(p)
 def test_exact_service_generation(self):
  pair=c.PAIRS[0];run=c.pair_info(pair)['runs']['native'];owner={'pid':123,'identity':{'uid':1016,'start_ticks':'555','cmdline':'test'}};job={'status':'success','name':run['run_id'],'service_pid':123,'service_identity':copy.deepcopy(owner['identity']),'graph_sha256':run['graph_sha256']}
  c.verify_job(job,'native',pair,owner,self.gate());job['service_identity']['start_ticks']='556'
  with self.assertRaises(ValueError):c.verify_job(job,'native',pair,owner,self.gate())
 def test_render_exact_prefix_and_equal_crop(self):
  for pair in c.PAIRS:
   n=c.pair_info(pair)['valid_frames'];cmd=r.command(['s.mp4','n.mp4','f.mp4'],'c.png','o.mp4',n,'ffmpeg',n);filters=cmd[cmd.index('-filter_complex')+1]
   self.assertEqual(filters.count(f'trim=start_frame=0:end_frame={n}'),3);self.assertEqual(filters.count('crop=1280:720:16:8'),3);self.assertNotIn('fps=',filters);self.assertNotIn('scale=',filters)
  self.assertEqual(r.LABELS,('1.参考视频','2.普通编辑','3.时序引导'))
 def test_short_video_not_padded_to_two_seconds(self):self.assertEqual(r.display_lengths(43),[('full_valid',43)])
 def test_full_prefix_and_first48(self):self.assertEqual(r.display_lengths(97),[('full_valid',97),('first2seconds',48)])
 def test_render_tail_not_allowed(self):
  with self.assertRaises(ValueError):r.command(['s','n','f'],'c','o',56,'ffmpeg',43)
 def test_six_times_include_endpoint(self):
  for pair in c.PAIRS:
   valid=c.pair_info(pair)['valid_frames'];frames=r.six_frames(valid);self.assertEqual(len(set(frames)),6);self.assertEqual(frames[0],0);self.assertEqual(frames[-1],valid-1);self.assertEqual(frames,sorted(frames))
 def test_physical_pts(self):
  a={'width':1312,'height':736,'count':56,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(56)]};r.check_time(a,56,1312,736);a['pts_s'][30]+=1/24
  with self.assertRaises(ValueError):r.check_time(a,56,1312,736)
 def test_denominator_pending_not_complete(self):
  with patch('pathlib.Path.exists',return_value=False):report=show.summary()
  self.assertEqual(report['fixed_denominator'],2);self.assertEqual(len(report['rows']),2);self.assertEqual(report['completed_pairs'],0);self.assertTrue(all(x['task_success']=='UNREVIEWED' and x['MF'] is None for x in report['rows']))
 def test_ssh_transient_retryable(self):
  with patch('remote.subprocess.run',side_effect=subprocess.CalledProcessError(255,['ssh'],stderr='network unavailable')):
   with self.assertRaises(ConnectionError):remote.read_paths([c.config()['producer_remote']+'/test.json'])
 def test_remote_validation_not_transient(self):
  with patch('remote.subprocess.run',side_effect=subprocess.CalledProcessError(1,['ssh'],stderr='invalid evidence')):
   with self.assertRaises(subprocess.CalledProcessError):remote.read_paths([c.config()['producer_remote']+'/test.json'])
 def test_static_assets_match(self):
  c.validate_static()
  for pair in c.PAIRS:
   for name in ['source','provenance','source_original']:
    rec=c.pair_info(pair)[name];self.assertEqual(c.sha(c.ROOT/rec['file']),rec['sha256'])
 def test_bind_rejects_mismatched_started_generation(self):
  cfg=c.config();root=Path(cfg['producer_remote']);owner={'pid':1,'identity':{'start_ticks':'111'}}
  data={str(root/'deploy_manifest.json'):{'sha256':cfg['producer_seal_sha256']},str(root/'configs/scientific_contract.json'):{'sha256':cfg['producer_contract_sha256']},str(root/'configs/runtime.json'):{'sha256':cfg['producer_runtime_sha256'],'value':{}},str(root/'audit/trial/STARTED.json'):{'value':{'owner':{'pid':2},'controller':{},'unix':1}},str(root/'processes/service.json'):{'value':owner}}
  with patch.object(bind_execution,'read_paths',return_value=data),self.assertRaisesRegex(ValueError,'STARTED'):bind_execution.bind('trial')
 def test_status_preserves_verifier_failure(self):
  cfg=c.config();root=Path(cfg['producer_remote']);owner={'pid':1};pair=c.PAIRS[0];data={str(root/'deploy_manifest.json'):{'sha256':cfg['producer_seal_sha256']},str(root/'processes/service.json'):{'value':owner},str(root/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json'):None,str(root/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE_FAILURE.json'):{'sha256':'failurehash','value':{'error':'fixture invalid data'}}}
  with patch.object(collect_pair,'read',return_value={'producer_seal_sha256':cfg['producer_seal_sha256'],'owner':owner}),patch.object(collect_pair,'read_paths',return_value=data):self.assertEqual(collect_pair.status(pair)['status'],'FAILED_GATE')
 def history_fixture(self):
  pair=c.PAIRS[0];p=c.pair_info(pair);g=self.gate(pair);graph=c.read(c.ROOT/'configs/graphs'/(p['runs']['native']['run_id']+'.json'))
  job={'prompt_id':'actual-fixture-prompt'};record={'filename':'fixture.mp4','subfolder':'case','type':'output'}
  g['runs']['native']['video']['file']=c.config()['producer_remote']+'/output/case/fixture.mp4'
  history={'status':{'completed':True,'status_str':'success'},'prompt':[1,job['prompt_id'],graph], 'outputs':{'14':{'images':[record]}}}
  return history,job,graph,g
 def test_actual_history_prompt_and_output(self):
  h,j,graph,g=self.history_fixture();c.verify_history(h,j,graph,'native',c.PAIRS[0],g)
  h['prompt'][1]='another-run'
  with self.assertRaisesRegex(ValueError,'prompt ID'):c.verify_history(h,j,graph,'native',c.PAIRS[0],g)
 def test_actual_prompt_edit_rejected(self):
  h,j,graph,g=self.history_fixture();graph['5']['inputs']['prompt']='modified prompt'
  with self.assertRaisesRegex(ValueError,'P1 prompt'):c.verify_history(h,j,graph,'native',c.PAIRS[0],g)
 def test_actual_output_name_rejected(self):
  h,j,graph,g=self.history_fixture();h['outputs']['14']['images'][0]['filename']='other.mp4'
  with self.assertRaisesRegex(ValueError,'paths differ'):c.verify_history(h,j,graph,'native',c.PAIRS[0],g)
 def test_reference_image_absence_and_scope(self):
  for pair in c.PAIRS:
   p=c.pair_info(pair);self.assertIs(p['reference_image_used'],False);self.assertEqual(p['reference_image_count'],0)
  self.assertEqual(c.pair_info('short_0114')['clip']['original_frame_interval_half_open'],[0,109])
  self.assertEqual(c.pair_info('long_0039')['clip']['original_frame_interval_half_open'],[0,150])
  self.assertIn('not official full-length score',c.pair_info('long_0039')['evaluation_scope'])
 def test_one_shot_pending_never_collects(self):
  with patch.object(consume_pair,'validate_static'),patch.object(consume_pair,'read',return_value={'attempt':'test'}),patch('pathlib.Path.exists',return_value=True),patch.object(consume_pair.collect_pair,'status',return_value={'status':'PENDING_GATE'}),patch.object(consume_pair,'save'),patch.object(consume_pair.collect_pair,'collect') as collect:
   result=consume_pair.run(c.PAIRS[0],'test','/tmp/unwritten.html')
   self.assertEqual(result['status'],'PENDING_GATE');collect.assert_not_called()
 def test_one_shot_wrong_attempt_rejected(self):
  with patch.object(consume_pair,'validate_static'),patch.object(consume_pair,'read',return_value={'attempt':'old'}),patch('pathlib.Path.exists',return_value=True),self.assertRaisesRegex(ValueError,'different attempt'):
   consume_pair.run(c.PAIRS[0],'new','/tmp/unwritten.html')
 def test_embedded_media_bytes(self):
  import base64,hashlib
  video=b'cpu-fixture-video';image=b'cpu-fixture-poster';h=lambda b:hashlib.sha256(b).hexdigest();uri=lambda mime,b:'data:'+mime+';base64,'+base64.b64encode(b).decode()
  doc=f'<video controls preload="none" poster="{uri("image/jpeg",image)}" src="{uri("video/mp4",video)}"></video>'
  manifest={'embedded_video_count':1,'embedded_assets':[{'role':'full_valid','sha256':h(video)},{'role':'poster','sha256':h(image)}]}
  self.assertTrue(verify_showcase.validate_embedded(doc,manifest)['passed'])
  with self.assertRaises(ValueError):verify_showcase.validate_embedded(doc.replace(uri('video/mp4',video),'/absolute/local.mp4'),manifest)
  manifest['embedded_assets'][0]['sha256']='wrong'
  with self.assertRaises(ValueError):verify_showcase.validate_embedded(doc,manifest)
 def test_pending_page_has_no_fake_video(self):
  with patch('pathlib.Path.exists',return_value=False):report=show.summary()
  self.assertEqual(report['media_ready_pairs'],0)
  self.assertTrue(verify_showcase.validate_embedded('<p>等待实际成片</p>',{'embedded_video_count':0,'embedded_assets':[]})['passed'])
if __name__=='__main__':unittest.main()
