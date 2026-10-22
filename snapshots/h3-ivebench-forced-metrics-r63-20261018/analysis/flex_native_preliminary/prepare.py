from pathlib import Path
import hashlib, json, subprocess
from PIL import Image, ImageDraw, ImageFont
R=Path(__file__).resolve().parent
C=Path('/Users/researcher/DevProjects/h3-flexiact-forced-metrics-r65-20261018/inputs')
N='r65_fitness_seed2026101701_native'
E=R/'evidence'; M=R/'media'; F=M/'frames'; F.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
j=json.loads((E/f'{N}_job.json').read_text()); h=json.loads((E/f'{N}_history.json').read_text()); g=json.loads((E/f'{N}.json').read_text())
case=j['case_binding']['case']; source=C/case['video']; portrait=C/case['portrait']; native=M/f'{N}_00001_.mp4'
assert j['status']=='success' and h['status']['completed'] and h['status']['status_str']=='success'
assert j['prompt_id']==h['prompt'][1]==j['response']['prompt_id']
assert h['prompt'][2]==g and sha(E/f'{N}.json')==j['graph_sha256']
assert h['outputs']['14']['images']==[{'filename':native.name,'subfolder':'','type':'output'}]
assert sha(native)=='4e16603afc4d4a384ce11932b05693ab7268efbf5b7e32b03b5018a70c37f217'
assert sha(source)==case['video_sha256'] and sha(portrait)==case['portrait_sha256']
assert sha(C/case['provenance'])==case['provenance_sha256']
inds=[0,12,24,36,48,60]; probe={}; assets=[]
for label, p in [('source',source),('native',native)]:
    q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-show_streams','-show_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,start_time:frame=best_effort_timestamp_time','-of','json',str(p)]))
    assert len(q['frames'])==158 and q['streams'][0]['width']==1152 and q['streams'][0]['height']==768
    assert q['streams'][0]['avg_frame_rate']=='24/1'
    pts=[float(x['best_effort_timestamp_time']) for x in q['frames']]
    assert all(abs(t-i/24)<1e-5 for i,t in enumerate(pts))
    probe[label]={'stream':q['streams'][0], 'frame_pts':pts,'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
    for i in inds:
        out=F/f'{label}_{i:03}.png'
        subprocess.run(['/opt/homebrew/bin/ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(p),'-vf',f'select=eq(n\\,{i})','-frames:v','1',str(out)],check=True)
        assets.append({'file':str(out.relative_to(R)),'sha256':sha(out),'source':label,'frame_index':i,'pts_seconds':pts[i]})
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',24)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
W,H=576,384; cap=48
canvas=Image.new('RGB',(2*W,len(inds)*(H+cap)),(0,0,0)); d=ImageDraw.Draw(canvas)
for row,i in enumerate(inds):
    for col,label in enumerate(['source','native']):
        im=Image.open(F/f'{label}_{i:03}.png').convert('RGB').resize((W,H),Image.Resampling.LANCZOS)
        canvas.paste(im,(col*W,row*(H+cap)))
        d.text((col*W+12,row*(H+cap)+H+9),f'{"Reference video" if label=="source" else "Edited video"} | {i/24:.1f} s | frame {i:03}',font=small,fill='white')
    pair=Image.new('RGB',(2304,816),(0,0,0));pd=ImageDraw.Draw(pair)
    for col,label in enumerate(['source','native']):
        pair.paste(Image.open(F/f'{label}_{i:03}.png').convert('RGB'),(col*1152,0));pd.text((col*1152+16,780),f'{label.upper()} | {i/24:.1f} s | frame {i:03}',font=font,fill='white')
    pair.save(M/f'pair_{i:03}.png')
canvas.save(M/'fitness_six_times_source_native.png')
binding={'passed':True,'scope':'preliminary visual only; six fixed source/native timestamps; full paired quantitative evaluation pending','run_id':N,'prompt_id':j['prompt_id'],'graph_sha256':j['graph_sha256'],'checks':{'job_history_success':True,'prompt_ids_equal':True,'submitted_graph_equals_history_graph':True,'output_filename_bound_to_history':True,'remote_local_video_sha256_equal':True,'source_portrait_provenance_sha256_match_job':True,'same_geometry_and_all_frame_pts':True},'timestamp_seconds':[i/24 for i in inds],'frame_indices':inds,'inputs':probe,'portrait':{'file':str(portrait),'sha256':sha(portrait)},'actual_prompt':case['prompt'],'assets':assets,'contact_sheet':{'file':str(M/'fitness_six_times_source_native.png'),'sha256':sha(M/'fitness_six_times_source_native.png')}}
(E/'ACTUAL_BINDING.json').write_text(json.dumps(binding,indent=2)+'\n')
print(json.dumps({'passed':True,'sheet':binding['contact_sheet'],'video_sha256':sha(native)}))
