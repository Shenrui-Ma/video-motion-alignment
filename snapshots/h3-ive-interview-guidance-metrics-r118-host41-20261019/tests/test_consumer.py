import copy,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import consume,prepare,full_frame_review,render_media
class ConsumerTest(unittest.TestCase):
 def fixture(self):
  cfg=c.config();rt=c.read(c.ROOT/'configs/producer_runtime.json');run=cfg['runs']['forced'];owner=dict(pid=123,gpu_uuid=rt['gpu_uuid'],port=rt['port'],identity=dict(uid=rt['uid'],cmdline=str(Path(cfg['producer_remote'])/'scripts/service_entry.py')))
  g=dict(schema='r118-historical-native-guidance-runtime-gate-v1',passed=True,source_id='long_0047',prompt_version='P1-local-v1',checks={k:True for k in c.CHECKS},runtime_profile=rt,runtime_profile_sha256=cfg['producer_runtime_sha256'],service_owner=owner,runs=dict(native=cfg['expected_historical_native']),condition_tensor_files=[{}]*6)
  r=dict(run_id=run,NFE=20,Euler_updates=20,routed_blocks=450,valid_frames=97,evaluation_crop_xywh=[16,8,1280,720],video=dict(file=cfg['producer_remote']+'/output/result.mp4',properties=dict(width=1312,height=736,avg_frame_rate='24/1',nb_read_frames='107')),job_sha256='a'*64,history_sha256='b'*64)
  r['binding_artifacts']={f'configs/graphs/{run}.json':c.sha(c.ROOT/'configs/graph_forced.json'),f'logs/{run}_job.json':'a'*64,f'logs/{run}_history.json':'b'*64,'audit/noise.pt':'c'*64,'audit/x0/run/manifest.json':'d'*64};g['runs']['forced']=r;return cfg,g
 def test_actual_gate(self):
  cfg,g=self.fixture();self.assertEqual(c.verify_gate(g,cfg),g)
 def test_required_checks(self):
  for key in c.CHECKS:
   with self.subTest(key=key):
    cfg,g=self.fixture();del g['checks'][key]
    with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_false_additional_check(self):
  cfg,g=self.fixture();g['checks']['extra']=False
  with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_historical_native_provenance(self):
  cfg,g=self.fixture();g=copy.deepcopy(g);g['runs']['native']['video']['sha256']='0'*64
  with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_same_host_not_required(self):
  cfg,g=self.fixture();self.assertNotEqual(g['runs']['native']['runtime'],g['runtime_profile']);c.verify_gate(g,cfg)
 def test_valid_domain(self):
  for field,bad in [('valid_frames',107),('routed_blocks',400),('NFE',8),('evaluation_crop_xywh',[0,0,1280,720])]:
   with self.subTest(field=field):
    cfg,g=self.fixture();g['runs']['forced'][field]=bad
    with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_output_escape(self):
  cfg,g=self.fixture();g['runs']['forced']['video']['file']=cfg['producer_remote']+'/output/../x.mp4'
  with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_graph_binding(self):
  cfg,g=self.fixture();g['runs']['forced']['binding_artifacts'][f"configs/graphs/{cfg['runs']['forced']}.json"]='0'*64
  with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_owner(self):
  for key,bad in [('gpu_uuid','other'),('port',1)]:
   cfg,g=self.fixture();g['service_owner'][key]=bad
   with self.assertRaises(ValueError):c.verify_gate(g,cfg)
 def test_no_tensor_copy(self):
  cfg,g=self.fixture();x=consume.compact_artifacts(g);self.assertNotIn('audit/noise.pt',x);self.assertIn('audit/x0/run/manifest.json',x);self.assertTrue(all(Path(n).suffix=='.json' for n in x))
 def release_fixture(self):
  cfg,g=self.fixture();o=g['service_owner'];complete=dict(passed=True,GPU_released=True,jobs=[cfg['runs']['forced']],remaining=[],gates=dict(long_0047=dict(file=cfg['producer_remote']+'/analysis/postrun/long_0047/PAIR_RUNTIME_GATE.json',sha256='g'*64)));release=dict(passed=True,process_absent=True,CUDA_allocation_absent=True,owner=o);started=dict(owner=o);cleanup=dict(pid=o['pid'],process_absent=True,own_compute_absent=True);return cfg,g,complete,release,started,cleanup
 def test_exact_release(self):
  cfg,g,co,r,s,cl=self.release_fixture();c.verify_release(g,co,r,s,cl,'g'*64,cfg)
 def test_release_failures(self):
  for index,key,value in [(2,'GPU_released',False),(2,'remaining',['unfinished']),(3,'CUDA_allocation_absent',False),(5,'pid',999)]:
   x=list(self.release_fixture());x[index][key]=value
   with self.assertRaises(ValueError):c.verify_release(x[1],x[2],x[3],x[4],x[5],'g'*64,x[0])
 def test_full97_denominator(self):
  pages=full_frame_review.pages(97);self.assertEqual([x for row in pages for x in row],list(range(97)));self.assertEqual(len(pages),20)
 def test_pts_reject_retiming(self):
  s=dict(width=1312,height=736,count=107,avg_frame_rate='24/1',pts_s=[i/24 for i in range(107)]);render_media.check_time(s,107,1312,736);s['pts_s'][20]+=.01
  with self.assertRaises(ValueError):render_media.check_time(s,107,1312,736)
 def test_caption_and_geometry(self):
  im=render_media.caption_strip(render_media.choose_font());self.assertEqual(im.size,(3840,88));cmd=render_media.command(['s','n','g'],'caption','out',97,'ffmpeg');f=cmd[cmd.index('-filter_complex')+1];self.assertEqual(f.count('crop=1280:720:16:8'),3);self.assertNotIn('minterpolate',f);self.assertIn('end_frame=97',f)
 def test_review_inherits_without_claiming_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'ledger.json';p.write_text('{}');x=prepare.event_template(p);self.assertFalse(x['all_frames_inspected']);self.assertEqual(len(x['events']),5);self.assertTrue(all(e['forced_boundary_frames'] is None and e['forced_status']=='PENDING' for e in x['events']));self.assertIsNone(x['overall_timing'])
 def test_static(self):c.verify_static()
if __name__=='__main__':unittest.main()
