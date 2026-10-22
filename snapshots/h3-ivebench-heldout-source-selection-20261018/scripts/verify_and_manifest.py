"""Verify the frozen source selection and exact decoded-frame preparation evidence."""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
B=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x): (B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
freeze=json.loads((B/'SELECTION_FREEZE.json').read_text())
for e in freeze['files']:
 p=Path(e['file']);assert sha(p)==e['sha256'] and p.stat().st_size==e['bytes'], p
m=json.loads((B/'SELECTED_4_MANIFEST.json').read_text())
assert len(m['pairs'])==4 and m['denominators']['new_h3_outputs_examined']==0
entries=[]
for row in m['pairs']:
 id=row['pair_id'];p=B/'inputs'/f'{id}_provenance.json';r=json.loads(p.read_text())
 files={kind:B/'inputs'/f'{id}_{suffix}' for kind,suffix in [('video','video.mp4'),('original','original.mp4'),('prompt','prompt.txt'),('provenance','provenance.json')]}
 assert r['selection_sha256']==sha(B/'SELECTED_4_MANIFEST.json')
 assert sha(files['original'])==r['source_sha256']==row['source']['sha256']
 assert sha(files['video'])==r['video_sha256']
 assert sha(files['prompt'])==r['prompt_sha256']
 assert files['prompt'].read_text()==row['edit_prompt']+'\n'
 fps=Fraction(row['source']['fps_rational']);source_n=row['source']['frame_count']
 ts=[Fraction(i,1)/fps for i in range(source_n)]
 valid=math.ceil(ts[-1]*24)+1;total=17*math.ceil(Fraction(valid-5,17))+5
 mapping=[min(range(source_n),key=lambda i:(abs(ts[i]-Fraction(t,24)),i)) for t in range(valid)] + [source_n-1]*(total-valid)
 assert r['frames']==total and r['effective_frame_count']==valid
 assert r['evaluate_indices']==list(range(valid)) and r['padding_indices']==list(range(valid,total))
 assert r['input_to_original_frame']==mapping==row['input_protocol']['input_to_original_frame']
 assert r['input_frame_md5']==[r['original_transformed_frame_md5'][i] for i in mapping]
 assert r['decoded_pixel_mapping_exact'] is True
 assert r['geometry']==[1312,736] and r['content_rectangle_xywh']==[16,8,1280,720]
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','stream=codec_type,width,height,nb_frames,avg_frame_rate','-of','json',str(files['video'])]))
 assert len(probe['streams'])==1
 s=probe['streams'][0]
 assert s['codec_type']=='video' and [s['width'],s['height']]==[1312,736] and int(s['nb_frames'])==total and Fraction(s['avg_frame_rate'])==24
 entries.append({'pair_id':id,'edit_prompt':row['edit_prompt'],'frames':total,'effective_frame_count':valid,'padding_frames':total-valid,'fps':24,'canvas':[1312,736],'source_original_audio_present':any(x['codec_type']=='audio' for x in row['source']['av_streams']['streams']),'prepared_audio_present':False,'files':{k:{'file':str(v),'bytes':v.stat().st_size,'sha256':sha(v)} for k,v in files.items()},'frame_mapping_exact':True})
write('PREPARED_INPUTS_MANIFEST.json',{'schema':'r64-source-only-prepared-inputs-v1','status':'READY_FOR_COPY_CPU_VERIFIED_NO_H3_GENERATION','selection_sha256':sha(B/'SELECTED_4_MANIFEST.json'),'selection_freeze_sha256':sha(B/'SELECTION_FREEZE.json'),'expected_next_experiment':'R64 Native versus fixed-ON; actual model graph, seeds and capacity gates owned by root/builder','scope':'4 official object/background editing tasks with changing human movement, distinct from original5 person/clothing tasks','pairs':entries})
write('audit/VERIFICATION.json',{'pass':True,'frozen_entries_verified':len(freeze['files']),'selected_tasks':4,'prepared_frames':sum(x['frames'] for x in entries),'valid_frames':sum(x['effective_frame_count'] for x in entries),'all_source_LFS_hashes_verified':True,'exact_lossless_frame_mapping_verified_by_prepare':True,'independent_temporal_map_and_stream_checks':True,'source_only_exclusion':['short_0186'],'new_model_outputs_examined':0,'gpu_calls':0,'new_model_or_pose_calls':0})
print([(x['pair_id'],x['frames'],x['effective_frame_count']) for x in entries])
print('prepared manifest SHA',sha(B/'PREPARED_INPUTS_MANIFEST.json'))
