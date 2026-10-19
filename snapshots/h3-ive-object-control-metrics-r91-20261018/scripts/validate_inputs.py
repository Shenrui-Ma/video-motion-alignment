"""Actual CPU source hash/PTS check before any generated output is available."""
import argparse
from fractions import Fraction
from common import *
from render_pair import media_info,check_time,six_frames

def validate(ffprobe='ffprobe'):
 validate_static();rows=[]
 for pair in PAIRS:
  p=pair_info(pair);prov=read(ROOT/p['provenance']['file'])
  for role in ('source','source_original','provenance'):require(sha(ROOT/p[role]['file'])==p[role]['sha256'],'input changed: '+role)
  require(prov['video_sha256']==p['source']['sha256'] and prov['source_sha256']==p['source_original']['sha256'],'provenance source identity differs')
  require(prov['frames']==p['geometry']['frames'] and prov['effective_frame_count']==p['valid_frames'] and prov['fps']==24,'source frame contract differs')
  require(prov['reference_images']==[] and prov['content_rectangle_xywh']==p['evaluation_crop_xywh'],'source reference image/crop differs')
  require(prov['evaluate_indices']==list(range(p['valid_frames'])) and prov['padding_indices']==list(range(p['valid_frames'],p['geometry']['frames'])),'valid/padding domain differs')
  require(prov['clip']==p['clip'],'source clip mapping differs')
  info=media_info(ROOT/p['source']['file'],ffprobe);check_time(info,p['geometry']['frames'],1312,736)
  start=Fraction(p['clip']['start_pts_rational']);end=Fraction(p['clip']['end_exclusive_rational'])
  require(Fraction(p['valid_frames']-1,24)<end-start<=Fraction(p['valid_frames'],24),'24fps valid domain differs from rational source interval')
  rows.append({'pair':pair,'valid_frames':p['valid_frames'],'total_frames':p['geometry']['frames'],'fps':24,'reference_image_used':False,'source':p['source'],'source_original':p['source_original'],'clip_original_frame_interval':p['clip']['original_frame_interval_half_open'],'clip_original_pts_half_open':[str(start),str(end)],'six_fixed_frame_indices':six_frames(p['valid_frames']),'actual_prepared_pts_checked':True})
 return {'passed':True,'rows':rows,'GPU_started':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ffprobe',default='ffprobe');a=p.parse_args();value=validate(a.ffprobe);save(ROOT/'audit/INPUTS_CPU_VERIFIED.json',value,replace=True);print(json.dumps(value,indent=2))
