from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'tests/test_prompt_pair.py';s=p.read_text()
s=s.replace("c.read(ROOT/'configs/ancestors/r57_short_0210_seed2026101701_native.json')['5']['inputs']['prompt']","(ROOT/'configs/prompts/p1.txt').read_text()")
s=s.replace(" def test_changed_prompt_refused(self):",''' def test_original_noise_missing_is_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'design').mkdir();(root/'design/ORIGINAL_NOISE_READBACK.json').write_text(json.dumps({'file_sha256':'expected'}))
   with self.assertRaisesRegex(ValueError,'original noise cache missing or changed'):c.require_original_noise_cache(root)
 def test_original_noise_changed_is_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'design').mkdir();(root/'audit').mkdir();p=root/'audit/r75_source_51310_seed2026101701_noise.pt';p.write_bytes(b'actual')
   (root/'design/ORIGINAL_NOISE_READBACK.json').write_text(json.dumps({'file_sha256':c.sha(p)}));self.assertEqual(c.require_original_noise_cache(root),p)
   p.write_bytes(b'replaced')
   with self.assertRaisesRegex(ValueError,'original noise cache missing or changed'):c.require_original_noise_cache(root)
 def test_changed_prompt_refused(self):''')
p.write_text(s)
p=R/'tests/test_pair_verifier.py';s=p.read_text()
s=s.replace('fitness__game_man_5','source_51310').replace('R49_fitness_captures.json','R38_captures.json')
s=s.replace("'audit/tensor_blobs'","'audit/tensor_blobs','design'")
s=s.replace('range(0,147,3)','range(141)').replace('147','141').replace('[0,0,1152,768]','[0,0,1312,736]').replace("'width':1152,'height':768,'nb_read_frames':'158'","'width':1312,'height':736,'nb_read_frames':'141'")
s=s.replace('[1152,768]','[800,1216]').replace('[1,24,1,48,72]','[1,24,1,76,50]').replace('[1,768,1152,3]','[1,1216,800,3]').replace('[158,768,1152,3]','[141,736,1312,3]')
s=s.replace("'expected_DiT_visual_patch_tokens':864","'expected_DiT_visual_patch_tokens':950")
s=s.replace("'pixel_interval_inclusive':[0,146]","'pixel_interval_inclusive':[0,140]").replace("'frame_rows':864","'frame_rows':943").replace('[0,44]','[0,42]').replace('[0,148]','[0,140]').replace('44*864','42*943').replace('47*864','42*943')
s=s.replace('864,40608,526,40608','950,39606,470,39606')
anchor="  for arm,run in zip(('p0','p1'),self.runs):"
insert="""  self.put(r/'design/ORIGINAL_NOISE_READBACK.json',{'file_sha256':verify.sha(r/'audit'/f'{pair_id}_noise.pt'),'actual_tensor_streams':hashes,'signature':sig})
  self.put(r/'design/HISTORICAL_CONDITION_SIGNATURES.json',{'input_video':{'sha256':'rgb'}})
"""
assert s.count(anchor)==1;s=s.replace(anchor,insert+anchor)
s=s.replace(" def test_wrong_router_step_fails(self):",''' def test_new_noise_equal_between_arms_still_rejected_if_not_historical(self):
  p=self.root/'audit'/f'r75_{self.source}_seed2026101701_noise.pt';v=torch.load(p,weights_only=True);v['tensors'][0]+=1;v['hashes']=[{k:cap.signature(x)[k] for k in ('shape','dtype','sha256')} for x in v['tensors']];torch.save(v,p)
  for run in self.runs:
   f=self.root/'audit'/f'{run}_noise.json';n=verify.read(f);n['actual_noise_streams']=v['hashes'];self.put(f,n)
  result=verify.verify(self.root,self.source);self.assertTrue(result['checks']['actual_initial_AV_noise_equal']);self.assertFalse(result['checks']['original_AV_noise_exact']);self.assertFalse(result['passed'])
 def test_changed_original_raw_video_rejected_even_when_both_arms_match(self):
  for run in self.runs:
   f=self.root/'audit'/f'{run}_conditioning.json';c=verify.read(f);c['input_video']={'sha256':'new-RGB'};self.put(f,c)
  result=verify.verify(self.root,self.source);self.assertTrue(result['checks']['input_video_equal']);self.assertFalse(result['checks']['original_raw_input_video_exact']);self.assertFalse(result['passed'])
 def test_wrong_router_step_fails(self):''')
p.write_text(s)
