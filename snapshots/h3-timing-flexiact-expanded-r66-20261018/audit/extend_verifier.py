from pathlib import Path
r=Path(__file__).resolve().parents[1];p=r/'analysis/postrun/verify_pair.py';t=p.read_text().replace('SOURCES,GEOMETRY','SOURCES,GEOMETRY,SHAPES')
insert='''def reference_geometry_matches(c,case,plan):
 """Check both reference modalities and the actual packed layout for this target image."""
 image=case['reference_image_expected'];w,h=image['expected_native_ref_image_size_match_width_height']
 image_shape=image['expected_clean_reference_latent_shape'];tokens=image['expected_DiT_visual_patch_tokens']
 calls=c['native_vae_calls'];require(len(calls)==2,'expected image then video VAE calls')
 shapes_ok=(calls[0]['prepared_frames']['shape']==[1,h,w,3] and calls[0]['latent']['shape']==image_shape and calls[1]['prepared_frames']['shape']==[158,768,1152,3] and calls[1]['latent']['shape']==list(SHAPES['video']) and c['target_latent_shapes']==[list(SHAPES[k]) for k in ('video','audio')])
 actual=c['pair_snapshot']['actual'];refs=actual['references']
 shapes_ok=shapes_ok and [x['kind'] for x in refs]==['image','video'] and [x['clean_latent']['shape'] for x in refs]==[image_shape,list(SHAPES['video'])] and actual['target_latent_shapes']==c['target_latent_shapes']
 segments=c['packed_layout']['segments'];require(len(segments)==5,'unexpected silent image+video packed layout')
 sizes=[segments[0][1],tokens,40608,526,40608];labels=['text','ref_img','ref_img','audio','video'];offset=0;expected=[]
 for size,label in zip(sizes,labels):expected.append([offset,offset+size,label]);offset+=size
 layout_ok=(segments[0][0]==0 and segments[0][1]>0 and segments==expected and c['packed_layout']['seq_len']==offset and actual['packed_layout']['segments']==segments and actual['packed_layout']['seq_len']==offset and plan['reference_image_segments']==[segments[1][:2]] and plan['reference_video_segment']==segments[2][:2] and plan['target_video_segment']==segments[4][:2])
 return shapes_ok and layout_ok

'''
t=t.replace('def output_file(root,history):',insert+'def output_file(root,history):')
t=t.replace("'source_id':source,'prompt_version'", "'source_id':source,'pair_key':source,'motion_source_id':jobs[pair[0]]['case']['motion_source_id'],'original_pair_id':jobs[pair[0]]['case']['original_pair_id'],'group':jobs[pair[0]]['case']['group'],'prompt_version'")
t=t.replace("checks[arm+'_sampled_finite']=", "checks[arm+'_reference_geometry']=reference_geometry_matches(c,case,plan)\n  checks[arm+'_sampled_finite']=")
t=t.replace("len(hashes)==2 and saved['signature']", "len(hashes)==2 and [x['shape'] for x in hashes]==[list(SHAPES[k]) for k in ('video','audio')] and saved['signature']")
t=t.replace("p.add_argument('--source',choices=SOURCES,required=True)","p.add_argument('--pair','--source',dest='source',choices=SOURCES,required=True,help='action+target pair key; not a motion-only ID')")
p.write_text(t)
# Update inherited tests for the new registry without changing their numerical oracle.
p=r/'tests/test_first_pair.py';t=p.read_text().replace('registry,read,sha','registry,read,sha,PAIR_KEYS').replace("root/'analysis/postrun/fitness/PAIR_RUNTIME_GATE.json'","root/'analysis/postrun'/PAIR_KEYS[0]/'PAIR_RUNTIME_GATE.json'").replace("'source_id':'fitness'","'source_id':PAIR_KEYS[0]");p.write_text(t)
p=r/'tests/test_flex_support.py';t=p.read_text().replace(",'21','22'",'');t=t.replace("self.assertEqual(c['evaluation_indices'],list(range(0,147,3)))","self.assertEqual(c['evaluation_indices'],list(range(0,147,3)))\n   self.assertEqual(new['22']['inputs']['file'],c['video'])")
p.write_text(t)
p=r/'tests/test_pair_verifier.py';t=p.read_text().replace("self.source='fitness'","self.source=verify.SOURCES[0]")
t=t.replace("noise=[torch.zeros((2,)),torch.ones((3,))]","noise=[torch.zeros((1,2)),torch.ones((1,3))]")
t=t.replace("'case':{'prompt':'P0'", "'case':{'motion_source_id':'human2animal_1','original_pair_id':'extension/human2animal_1/movie_man_11','group':'official_assets_crosspair_extension','prompt':'P0'")
t=t.replace("patch.object(cap,'SHAPES',self.shapes)","patch.object(cap,'SHAPES',self.shapes),patch.object(verify,'SHAPES',self.shapes),patch.object(verify,'reference_geometry_matches',return_value=True)")
p.write_text(t)
