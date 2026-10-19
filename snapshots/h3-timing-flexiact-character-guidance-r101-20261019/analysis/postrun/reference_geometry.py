from r101_contract import require,SHAPES

def reference_geometry_matches(c,case,plan):
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
