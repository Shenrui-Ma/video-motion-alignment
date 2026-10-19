"""Prepare every source frame before source-only automatic 141-frame selection."""
import fcntl,hashlib,json,re,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[1];OUT=R/'assets/prepared'
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def probe(p):return json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,duration,time_base:frame=best_effort_timestamp_time','-of','json',str(p)]))
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
protocol=json.loads((R/'configs/source_selection_protocol.json').read_text())
for cid,cp in protocol['sources'].items():
 src=R/'assets/candidates'/f'{cid}.mp4';dst=OUT/f'{cid}_full24.mp4'
 if sha(src)!=cp['original_sha256']:raise ValueError('source changed')
 if dst.exists():raise ValueError('existing full preparation: preserve and inspect')
 filt='setpts=PTS-STARTPTS,showinfo@source,fps=24:round=near,showinfo@mapped,scale=1312:736:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1312:736:(ow-iw)/2:(oh-ih)/2,setsar=1'
 cmd=[FF,'-hide_banner','-nostdin','-threads','2','-i',str(src),'-vf',filt,'-an','-c:v','libx264','-crf','16','-preset','medium','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(dst)]
 out=subprocess.run(cmd,capture_output=True,text=True);(P/f'{cid}_prepare.log').write_text(out.stderr)
 if out.returncode:raise RuntimeError('ffmpeg failed '+cid)
 matches={name:[] for name in ['source','mapped']}
 for line in out.stderr.splitlines():
  for name in matches:
   if 'showinfo@'+name not in line:continue
   m=re.search(r'n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([^ ]+).*?checksum:([A-Fa-f0-9]+)',line)
   if m:matches[name].append({'frame':int(m[1]),'pts':int(m[2]),'time_s':float(m[3]),'preencode_checksum':m[4]})
 pr=probe(dst);s=pr['streams'][0];n=len(pr['frames'])
 if (s['width'],s['height'],s['r_frame_rate'])!=(1312,736,'24/1') or n!=len(matches['mapped']) or n<141:raise ValueError('full geometry/mapping')
 if any(abs(float(x['best_effort_timestamp_time'])-i/24)>1e-6 for i,x in enumerate(pr['frames'])):raise ValueError('full PTS')
 mapping=[]
 for m in matches['mapped']:
  candidates=[x for x in matches['source'] if x['preencode_checksum']==m['preencode_checksum']]
  if not candidates:raise ValueError('frame has no preencode match')
  chosen=min(candidates,key=lambda x:(abs(x['time_s']-m['time_s']),x['frame']))
  mapping.append({'prepared_frame':m['frame'],'prepared_time_s':m['frame']/24,'original_frame':chosen['frame'],'original_time_s':chosen['time_s'],'matching_checksum_source_frames':[x['frame'] for x in candidates],'unique_checksum_match':len(candidates)==1,'preencode_checksum':m['preencode_checksum']})
 manifest={'source_id':cid,'original_sha256':sha(src),'full_prepared_sha256':sha(dst),'protocol_sha256':sha(R/'configs/source_selection_protocol.json'),'command':cmd,'filter':filt,'probe':pr,'frame_map':mapping,'mapping_evidence':'showinfo pixel checksums before and after fps; before scale/encode. Duplicate checksum matches recorded explicitly.','source_pose_not_yet_read':True}
 (OUT/f'{cid}_full24_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'source':cid,'frames':n,'sha256':sha(dst)}),flush=True)
