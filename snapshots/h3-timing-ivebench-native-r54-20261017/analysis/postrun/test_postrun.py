import copy,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
import contract as c,consume,one_phase,remote_consume
P=c.read(c.HERE/'PROTOCOL.json');PRODUCER=c.read(Path(P['root_local'])/'configs/scientific_contract.json')
class ProtocolTests(unittest.TestCase):
 def test_five_pairs_exact_producer(self):
  self.assertTrue(c.check_declared_cases(P,PRODUCER));self.assertEqual([x['source_id'] for x in P['cases']],['short_0210','short_0230','short_0263','short_0352','short_0370']);self.assertEqual(c.sha(Path(P['root_local'])/'deploy_manifest.json'),P['producer_manifest_sha256'])
 def test_pair_order_identity_or_map_rejected(self):
  for mode in ('order','identity','source','map','geometry','count'):
   q=copy.deepcopy(P)
   if mode=='order':q['cases'].reverse()
   if mode=='identity':q['cases'][0]['prompt']='wrong'
   if mode=='source':q['cases'][0]['video_sha256']='wrong'
   if mode=='map':q['cases'][0]['valid_frame_count']=90
   if mode=='geometry':q['geometry']['frames']=141
   if mode=='count':q['cases'].pop()
   with self.subTest(mode=mode),self.assertRaises(ValueError):c.check_declared_cases(q,PRODUCER)
 def test_summary_native_and_map_rejected(self):
  for case in P['cases']:
   s={k:case[k] for k in ('run_id','source_id','seed')};s.update(passed=True,NFE=20,actual_routed_blocks=0,source_video_sha256=case['video_sha256'],padding_evaluated=False,decoded_frame_md5_equal=True,score_frame_indices=list(range(case['valid_frame_count'])))
   self.assertTrue(c.check_case_summary(s,case))
   for key,val in [('run_id','wrong'),('source_video_sha256','wrong'),('NFE',19),('actual_routed_blocks',1),('padding_evaluated',True),('decoded_frame_md5_equal',False),('score_frame_indices',list(range(90)))]:
    with self.assertRaises(ValueError):c.check_case_summary(dict(s,**{key:val}),case)
 def test_runtime_seal_and_exporter_exact(self):
  root=Path(P['root_local'])
  for rel,row in c.read(root/'deploy_manifest.json')['files'].items():self.assertEqual(c.sha(root/rel),row['sha256'])
  self.assertEqual(P['score_crop_xywh'],[16,8,1280,720])
 def test_stability_and_pending(self):
  self.assertEqual(one_phase.readiness({'status':'pending'},None,0,60),('pending',None));snap={'status':'success_files_present','token':'a'};mode,state=one_phase.readiness(snap,None,0,60);self.assertEqual(mode,'stabilizing');self.assertEqual(one_phase.readiness(snap,state,60,60)[0],'ready');self.assertEqual(one_phase.readiness(dict(snap,token='b'),state,61,60)[0],'stabilizing')
 def test_root_code_binding_required(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c.save(root/'PROTOCOL.json',{});c.save(root/'FREEZE.json',{'files':{}});c.save(root/'BINDING.json',{'approved_for_consumer_start':True,'protocol_sha256':c.sha(root/'PROTOCOL.json'),'consumer_freeze_sha256':'wrong'})
   with patch.object(one_phase,'HERE',root),patch.object(one_phase.subprocess,'run') as invoke,self.assertRaises(ValueError):one_phase.prepare()
   invoke.assert_not_called()
class InventoryTests(unittest.TestCase):
 def fixture(self,arc,complete):
  c.save(arc/'input.json',{'x':1});c.save(arc/'FILE_INVENTORY.json',{'input.json':{'sha256':c.sha(arc/'input.json')},'blob.pt':{'sha256':'remote-only'}})
  ds=['RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json']
  for name in ds:c.save(arc/name,{})
  if complete:
   ds+=['final/one/SUMMARY.json'];c.save(arc/'final/one/SUMMARY.json',{'result':1});c.save(arc/'CPU_COMPLETE.json',{'passed':True,'derived_outputs':ds});c.save(arc/'DERIVED_FILES.json',{n:c.sha(arc/n) for n in ds+['CPU_COMPLETE.json']})
 def test_archive_and_final_nonPT_inventory(self):
  for complete in (False,True):
   with tempfile.TemporaryDirectory() as d:self.fixture(Path(d),complete);consume.check_download(Path(d))
 def test_extra_or_omitted_derivative_rejected(self):
  for mode in ('extra','missing'):
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);self.fixture(p,True)
    if mode=='extra':c.save(p/'extra.json',{})
    else:(p/'final/one/SUMMARY.json').unlink()
    with self.assertRaises((ValueError,FileNotFoundError)):consume.check_download(p)
 def producer_fixture(self,r):
  manifest={'files':{}}
  for rel in ('processes/service.json','configs/queue.json','configs/runtime.json','configs/scientific_contract.json'):c.save(r/rel,{})
  for case in P['cases']:
   run=case['run_id'];c.save(r/f'configs/graphs/{run}.json',{'5':{'inputs':{'run_id':run+'_shared'}}});c.save(r/f'logs/{run}_history.json',{'status':{'completed':True,'status_str':'success'},'outputs':{'14':{'images':[{'type':'output','filename':run+'_00001_.mp4','subfolder':''}]}}});c.save(r/f'logs/{run}_job.json',{'status':'success'})
   for rel in (f'audit/{run}_conditioning.json',f'audit/router/{run}.json',f'audit/{run}_shared_conditioning.json'):c.save(r/rel,{})
   c.save(r/f'audit/{run}_noise.json',{'pair_id':run+'_pair'})
   names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt'];c.save(r/f'audit/x0/{run}/manifest.json',{'status':'complete','captures':[{'file':x} for x in names[:-1]],'final_sampler_result':{'file':names[-1]}})
   for rel in [f'audit/x0/{run}/'+x for x in names]+[f'audit/{run}_pair_noise.pt',f'output/{run}_00001_.mp4']:
    p=r/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
   for basename in (case['video'],case['provenance'],case['original_source'],case['source_id']+'_prompt.txt'):
    p=r/'inputs'/basename;p.parent.mkdir(exist_ok=True);p.write_bytes(b'fixture');manifest['files'][str(p.relative_to(r))]={}
   for key in ('video',):
    p=r/'input'/case[key];p.parent.mkdir(exist_ok=True);p.write_bytes(b'fixture')
  c.save(r/'deploy_manifest.json',manifest)
 def test_all20inputs_and_only5_actual_loader_copies(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.producer_fixture(root)
   with patch.object(remote_consume,'ROOT',root):rows=remote_consume.inventory()
   rel=[str(x.relative_to(root)) for x in rows];self.assertEqual(sum(x.startswith('inputs/') for x in rel),20);self.assertEqual(sum(x.startswith('input/') for x in rel),5);self.assertEqual(sum('/x0/' in x and x.endswith('.pt') for x in rel),105);self.assertEqual(sum(x.startswith('output/') for x in rel),5)
 def test_missing_or_extra_capture_rejected(self):
  for extra in (False,True):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);self.producer_fixture(root);p=root/'audit/x0'/P['cases'][0]['run_id']
    if extra:(p/'extra.pt').write_bytes(b'x')
    else:(p/'x0_step000.pt').unlink()
    with patch.object(remote_consume,'ROOT',root),self.assertRaises(ValueError):remote_consume.inventory()
class CleanupTests(unittest.TestCase):
 def test_waits_for_exact_cleanup(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);arc=root/'archive';arc.mkdir();owner={'pid':123,'identity':{'start':'fixed'}}
   with patch.object(remote_consume,'ROOT',root),patch.object(remote_consume,'ARC',arc),patch.object(remote_consume,'checked_archive',return_value=owner):
    self.assertEqual(remote_consume.status()['phase'],'await_root_release')
    c.save(root/'processes/cleanup.json',{'pid':124,'service_record':owner,'process_absent':True,'own_compute_absent':True})
    with self.assertRaises(ValueError):remote_consume.status()
    c.save(root/'processes/cleanup.json',{'pid':123,'service_record':owner,'process_absent':True,'own_compute_absent':True})
    self.assertEqual(remote_consume.status(),{'phase':'case','run':P['cases'][0]['run_id']})

class ReleaseTests(unittest.TestCase):
 def test_exact_frame_time_grid(self):
  import release_prefix as r
  value={'streams':[{'width':1280,'height':720,'r_frame_rate':'24/1','avg_frame_rate':'24/1'}], 'frames':[{'best_effort_timestamp_time':str(i/24)} for i in range(87)]}
  self.assertEqual(len(r.check_video_grid(value,87,1280,720)),87)
  for mode in ('count','nan','time','size'):
   v=copy.deepcopy(value)
   if mode=='count':v['frames'].pop()
   if mode=='nan':v['frames'][2]['best_effort_timestamp_time']='nan'
   if mode=='time':v['frames'][2]['best_effort_timestamp_time']='0.5'
   if mode=='size':v['streams'][0]['width']=1312
   with self.assertRaises(ValueError):r.check_video_grid(v,87,1280,720)
 def test_real_prepared_source_lossless(self):
  import release_prefix as r
  root=Path(P['root_local']);case=P['cases'][0]
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d)/'source.mp4'
   result=r.source_view(root/'inputs'/case['video'],root/'inputs'/case['original_source'],root/'inputs'/case['provenance'],dest)
   self.assertTrue(result['decoded_pixel_mapping_exact']);self.assertEqual(len(result['score_frame_md5']),87)
   self.assertEqual(result['input_indices'],list(range(87)))
   copied=Path(d)/'reused.mp4'
   reused=r.reuse_source(root/'inputs'/case['video'],root/'inputs'/case['original_source'],root/'inputs'/case['provenance'],dest,copied)
   self.assertTrue(reused['reused_same_bytes']);self.assertEqual(r.sha(copied),r.sha(dest))
   altered=Path(d)/'changed.json';v=json.loads((root/'inputs'/case['provenance']).read_text());v['video_sha256']='wrong';altered.write_text(json.dumps(v))
   with self.assertRaises(ValueError):r.reuse_source(root/'inputs'/case['video'],root/'inputs'/case['original_source'],altered,dest,Path(d)/'bad.mp4')
class SourcePublishTests(unittest.TestCase):
 def test_incomplete_transfer_defers_without_output(self):
  import source_scores as publisher
  case=P['cases'][0]
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);dest=root/'scores';(root/'inputs').mkdir()
   with patch.object(publisher,'ROOT',root),patch.object(publisher,'DEST',dest):
    self.assertIsNone(publisher.publish(case))
    for key in ('video','provenance','original_source'):(root/'inputs'/case[key]).write_bytes(b'partial transfer')
    self.assertIsNone(publisher.publish(case));self.assertFalse(dest.exists())
if __name__=='__main__':unittest.main()

