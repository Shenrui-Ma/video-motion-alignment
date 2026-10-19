"""CPU actual-output verifier, one fresh P0/P1 Native pair. Quality is assessed separately."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,checked_snapshot,inspect_blob,condition_files,signature,expected_routing
from r84_contract import read,sha,require,registry,validate_job,SOURCES,GEOMETRY,SHAPES,prompt_pair_condition_checks
from execution_gate import atomic

def semantic_condition(c):
 return {k:v for k,v in c.items() if k!='run_id'}

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)

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

def output_file(root,history):
 images=history['outputs']['14']['images'];require(len(images)==1,'expected one final video')
 record=images[0];require(record.get('type')=='output','final file is not in output')
 rel=Path(record.get('subfolder',''))/record['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe final video path')
 file=root/'output'/rel;require(file.is_file() and not file.is_symlink(),'final video missing')
 return file

def video_properties(path):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,timeout=120,check=True)
 streams=json.loads(result.stdout)['streams'];require(len(streams)==1,'expected exactly one video stream');s=streams[0]
 require(s['width']==1152 and s['height']==768 and int(s['nb_read_frames'])==158 and s['avg_frame_rate']=='24/1','final geometry/frame count/fps differs')
 return s

