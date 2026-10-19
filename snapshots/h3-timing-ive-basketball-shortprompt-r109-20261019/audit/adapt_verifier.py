"""Adapt the inherited ordinary-control audit to this exact video-only source."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'analysis/postrun/verify_native.py';s=p.read_text()
start=s.index('def reference_geometry_matches(');end=s.index('\ndef output_file',start)
s=s[:start]+'''def reference_geometry_matches(c,case,plan):
 calls=c['native_vae_calls'];require(len(calls)==1,'expected one video VAE call')
 actual=c['pair_snapshot']['actual'];refs=actual['references']
 shapes_ok=(calls[0]['prepared_frames']['shape']==[107,736,1312,3] and calls[0]['latent']['shape']==list(SHAPES['video']) and c['target_latent_shapes']==[list(SHAPES[k]) for k in ('video','audio')] and [x['kind'] for x in refs]==['video'] and [x['clean_latent']['shape'] for x in refs]==[list(SHAPES['video'])] and actual['target_latent_shapes']==c['target_latent_shapes'])
 segments=c['packed_layout']['segments'];require(len(segments)==4,'expected text/video-reference/audio/target-video segments')
 sizes=[segments[0][1],30176,356,30176];labels=['text','ref_img','audio','video'];offset=0;expected=[]
 for size,label in zip(sizes,labels):expected.append([offset,offset+size,label]);offset+=size
 layout_ok=(segments[0][0]==0 and segments[0][1]>0 and segments==expected and c['packed_layout']['seq_len']==offset and actual['packed_layout']['segments']==segments and actual['packed_layout']['seq_len']==offset and plan['reference_image_segments']==[] and plan['reference_video_segment']==segments[1][:2] and plan['target_video_segment']==segments[3][:2])
 return shapes_ok and layout_ok
''' + s[end:]
s=s.replace("s['width']==1152 and s['height']==768 and int(s['nb_read_frames'])==158", "s['width']==1312 and s['height']==736 and int(s['nb_read_frames'])==107")
s=s.replace("runtime_keys=('host','gpu_uuid','core'", "runtime_keys=('host','core'")
s=s.replace("len(condition_files(c))==8,'expected eight actual condition tensors'", "len(condition_files(c))==6,'expected six actual condition tensors'")
s=s.replace("'step_interval_half_open':[0,20],'pixel_interval_inclusive':[0,146]", "'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,104]")
s=s.replace("plan['frame_rows']==864 and plan['latent_interval_half_open']==[0,44] and plan['position_bin_coverage_inclusive']==[0,148] and len(plan['reference_image_segments'])==1", "plan['frame_rows']==943 and plan['latent_interval_half_open']==[0,32] and plan['position_bin_coverage_inclusive']==[0,106] and len(plan['reference_image_segments'])==0")
s=s.replace("'valid_frames':147,'evaluation_indices':list(range(0,147,3))", "'valid_frames':105,'evaluation_indices':list(range(105)),'evaluation_crop_xywh':[16,8,1280,720]")
s=s.replace("'prompt_version':'P1'", "'prompt_version':'plain-exact-v1'")
s=s.replace("'parent_R100_P0_gate_sha256'", "'parent_R100_P1_gate_sha256'")
s=s.replace("'runtime_profile':runtime,", "'runtime_profile':runtime,'device_difference':{'parent_gpu_uuid':parent_runtime['gpu_uuid'],'current_gpu_uuid':runtime['gpu_uuid'],'same_host':True},")
s=s.replace('single P1 Native with actual R100 P0', 'single exact-short-prompt Native with actual R100 P1')
p.write_text(s)
