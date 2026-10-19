"""One fixed official source, original frames -> three repeats + terminal padding."""
import argparse,fcntl,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
FFMPEG='/opt/homebrew/bin/ffmpeg';FFPROBE='/opt/homebrew/bin/ffprobe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def probe(p):return json.loads(subprocess.check_output([FFPROBE,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)],text=True))
def frame_hashes(p,vf=None):
 cmd=[FFMPEG,'-v','error','-threads','2','-i',str(p),'-an']
 if vf:cmd+=['-vf',vf]
 cmd+=['-pix_fmt','yuv420p','-threads','2','-f','framemd5','-']
 return [line.split(',')[-1].strip() for line in subprocess.check_output(cmd,text=True).splitlines() if line and not line.startswith('#')]
def main():
 a=argparse.ArgumentParser();a.add_argument('source',choices=['chest','crouch','fitness','one_leg','rotate']);v=a.parse_args()
 with LOCK.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('BUSY');return 75
  signal.alarm(120);t=time.monotonic();binding=json.loads((ROOT/'design/PILOT_5_PAIR_BINDING.json').read_text());row=next(x for x in binding['pairs'] if x['action']==v.source)
  for k in ('source','target'):
   p=Path(row[k]['local_path']);assert sha(p)==row[k]['official_lfs_sha256']
  original=ROOT/'inputs'/f'source_{v.source}_original.mp4';portrait=ROOT/'inputs'/('source_'+v.source+'_portrait'+Path(row['target']['local_path']).suffix);caption=ROOT/'inputs'/f'source_{v.source}_official_caption.txt';out=ROOT/'inputs'/f'source_{v.source}_video.mp4'
  assert not out.exists(),'refusing overwrite'
  for source,dest in [(Path(row['source']['local_path']),original),(Path(row['target']['local_path']),portrait),(Path(row['caption_file']),caption)]:shutil.copyfile(source,dest)
  raw=probe(original);frames=raw['frames'];assert len(frames)==49 and all((x['width'],x['height'])==(720,480) for x in frames)
  assert all(abs(float(x['best_effort_timestamp_time'])-i/8)<1e-6 for i,x in enumerate(frames))
  vf='scale=1152:768:flags=lanczos,fps=24:round=near,tpad=stop_mode=clone:stop=11,trim=end_frame=158,setpts=N/(24*TB),setsar=1'
  cmd=[FFMPEG,'-v','error','-threads','2','-i',str(original),'-an','-vf',vf,'-c:v','libx264','-crf','0','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]
  subprocess.run(cmd,check=True,timeout=60);pr=probe(out);f=pr['frames'];assert len(f)==158
  assert all((x['width'],x['height'])==(1152,768) and abs(float(x['best_effort_timestamp_time'])-i/24)<1e-6 for i,x in enumerate(f))
  source_hash=frame_hashes(original,'scale=1152:768:flags=lanczos,setsar=1');input_hash=frame_hashes(out)
  mapping=[min(i//3,48) for i in range(158)];assert len(source_hash)==49 and input_hash==[source_hash[i] for i in mapping]
  dump(ROOT/'design'/f'INPUT_PROBE_{v.source}.json',pr)
  provenance={'source_id':v.source,'official_pair':row,'source_original_sha256':sha(original),'video_sha256':sha(out),'portrait_sha256':sha(portrait),'portrait_filename':portrait.name,'caption_sha256':sha(caption),'caption_in_inference':False,'command':cmd,'geometry':{'source':[720,480],'scaled':[1152,768],'crop':None},'frames':158,'fps':24,'input_to_original':mapping,'evaluate_indices':[i*3 for i in range(49)],'evaluate_seconds':[i/8 for i in range(49)],'terminal_padding_frames':11,'source_scaled_frame_md5':source_hash,'input_frame_md5':input_hash,'all158_decoded_frames_match_declared_source_exactly':True,'inference_observed':False,'elapsed_seconds':time.monotonic()-t}
  dump(ROOT/'inputs'/f'source_{v.source}_provenance.json',provenance)
  print(json.dumps({'source':v.source,'sha256':sha(out),'seconds':provenance['elapsed_seconds'],'exact_frame_map':True}));return 0
if __name__=='__main__':raise SystemExit(main())
