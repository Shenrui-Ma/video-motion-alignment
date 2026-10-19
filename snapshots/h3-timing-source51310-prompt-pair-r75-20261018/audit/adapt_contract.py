from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'scripts/r75_contract.py';s=p.read_text()
s=s.replace('short_0210','source_51310').replace("'frames':90","'frames':141").replace('(1,24,27,46,82)','(1,24,42,46,82)').replace('(1,32,2,150)','(1,32,2,235)')
start=s.index('def prompt_values(');end=s.index('\ndef expected_graph(',start)
s=s[:start]+'''def prompt_values(root=ROOT):
 root=Path(root);a=read(root/'configs/prompt_ancestry.json');values={}
 for file,key in [('CONTROL_DESIGN.json','control_design_sha256'),('ORIGINAL_NOISE_READBACK.json','historical_noise_readback_sha256'),('HISTORICAL_CONDITION_SIGNATURES.json','historical_conditions_sha256')]:
  require(sha(root/'design'/file)==a[key],'frozen historical design binding changed')
 for arm in ARMS:
  b=a[arm];p=root/b['file'];require(sha(p)==b['sha256'],'frozen prompt changed');values[arm]=p.read_text()
 parent=root/'configs/parent_graphs/r38_source51310_native.json'
 require(sha(parent)==a['parent_graph_sha256'] and read(parent)['5']['inputs']['prompt']==values['p0'],'historical P0 parent changed')
 design=read(root/'design/CONTROL_DESIGN.json')
 for arm in ARMS:require(a[arm]['sha256']==design[arm.upper()]['sha256'],'audited prompt design differs')
 return values
''' +s[end:]
s=s.replace('end_frame=89','end_frame=140').replace("case['reference_image_count']==0 and case['valid_frame_count']==87","case['reference_image_count']==1 and case['valid_frame_count']==141")
s=s.replace("read(parent)['5']['inputs']['prompt']==prompts['p0']==case['original_task']['edit_prompt']","read(parent)['5']['inputs']['prompt']==prompts['p0']")
s=s.replace("for key in ('video','provenance'):","for key in ('video','portrait','provenance'):")
s=s.replace("('native',1.,0,0,0,89,0,50,0,20)","('native',1.,0,0,0,140,0,50,0,20)")
anchor="  parent=root/case['parent_graph'];"
insert="""  design=read(root/'design/CONTROL_DESIGN.json')
  for key in ('video','portrait','provenance'):
   name=case[key];require(name in design['assets'] and case[key+'_sha256']==design['assets'][name]['sha256'],'historical asset identity changed')
  require(case['evaluation_indices']==list(range(141)) and case['evaluation_fps']==24 and case['evaluation_crop_xywh']==[0,0,1312,736],'evaluation scope changed')
  require(case['reference_image_expected']=={'expected_native_ref_image_size_match_width_height':[800,1216],'expected_clean_reference_latent_shape':[1,24,1,76,50],'expected_DiT_visual_patch_tokens':950},'portrait geometry changed')
"""
assert s.count(anchor)==1;s=s.replace(anchor,insert+anchor)
start=s.index('def prepare_loader_inputs(');end=s.index('\ndef prompt_pair_condition_checks(',start)
s=s[:start]+'''def require_original_noise_cache(root=ROOT):
 root=Path(root);expected=read(root/'design/ORIGINAL_NOISE_READBACK.json');cache=root/'audit/r75_source_51310_seed2026101701_noise.pt'
 require(cache.is_file() and not cache.is_symlink() and sha(cache)==expected['file_sha256'],'original noise cache missing or changed')
 return cache

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 require_original_noise_cache(root)
 for key in ('video','portrait'):
  path=folder/case[key]
  if not path.exists():
   with (root/'inputs'/case[key]).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
  require(not path.is_symlink() and sha(path)==case[key+'_sha256'],'loader source changed')
 return row
''' +s[end:]
p.write_text(s)
p=R/'scripts/preflight.py';s=p.read_text().replace("physical_frames':[0,89]","physical_frames':[0,140]").replace('all27 temporal bins','all42 temporal bins')
s=s.replace('  import service','  from r75_contract import require_original_noise_cache\n  require_original_noise_cache(root)\n  import service');p.write_text(s)
p=R/'analysis/postrun/verify_pair.py';s=p.read_text().replace('[158,768,1152,3]','[141,736,1312,3]').replace('40608','39606').replace('526','470')
s=s.replace("s['width']==1152 and s['height']==768 and int(s['nb_read_frames'])==158","s['width']==1312 and s['height']==736 and int(s['nb_read_frames'])==141")
s=s.replace("'pixel_interval_inclusive':[0,146]","'pixel_interval_inclusive':[0,140]").replace("plan['frame_rows']==864","plan['frame_rows']==943").replace('[0,44]','[0,42]').replace('[0,148]','[0,140]').replace('44*864','42*943').replace("'evaluation_fps':8","'evaluation_fps':24")
s=s.replace(" checks['actual_initial_AV_noise_equal']=", " original=read(root/'design/ORIGINAL_NOISE_READBACK.json');historical=read(root/'design/HISTORICAL_CONDITION_SIGNATURES.json')\n checks['original_AV_noise_exact']=(sha(cache)==original['file_sha256'] and all(noises[a]['actual_noise_streams']==original['actual_tensor_streams'] and noises[a]['signature']==original['signature'] for a in ('p0','p1')))\n checks['original_raw_input_video_exact']=all(conditions[a]['input_video']==historical['input_video'] for a in ('p0','p1'))\n checks['actual_initial_AV_noise_equal']=")
p.write_text(s)
