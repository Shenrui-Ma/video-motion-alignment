"""Read-only final source audit, one bounded shared-lock phase."""
import fcntl, hashlib, json, signal, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def main():
 with LOCK.open('a+') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('BUSY');return 75
  signal.alarm(120);t=time.perf_counter();rows=[]
  registry=ROOT.parent/'SCREENING_REGISTRY_20261017.json';before=sha(registry)
  for id,start,expected in [('10264579',366,'6da83aff11e242670f3da7d70fea14a5f4261deef7e67c0579dde7c2212babc2'),('6980766',192,'a05c350252bb6c7b5c63f2ed7d72dc4519a15cf91b43a56a8e6fda5210a4a44f')]:
   original=ROOT/'originals'/f'pexels_{id}_original.mp4'
   clip=ROOT/'inspection'/f'pexels{id}'/f'clip_start{start:04d}_141f24.mp4'
   grid=clip.parent/f'selected_{start:04d}.jpg'
   assert sha(original)==expected
   probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-threads','4','-count_frames','-show_streams','-show_format','-of','json',str(clip)],timeout=60))
   s=probe['streams'][0]
   assert len(probe['streams'])==1 and s['codec_type']=='video'
   assert s['r_frame_rate']==s['avg_frame_rate']=='24/1'
   assert int(s['nb_read_frames'])==int(s['nb_frames'])==141
   assert abs(float(s['duration'])-141/24)<1e-6
   assert (s['width'],s['height'])==(4096,2160)
   rows.append({'id':id,'original':str(original),'original_sha256':expected,'clip':str(clip),'clip_sha256':sha(clip),'grid':str(grid),'grid_sha256':sha(grid),'normalized_24fps_source_indices_inclusive':[start,start+140],'source_timestamps_first_last':[start/24,(start+140)/24],'source_end_exclusive_s':(start+141)/24,'clip_timestamps_first_last':[0,140/24],'duration_s':141/24,'decoded_frames':141,'fps':24,'width':4096,'height':2160,'probe':probe})
  assert sha(registry)==before
  out={'status':'PASS','scope':'source only; all original pixels before H3','cpu_threads_max':4,'seconds':time.perf_counter()-t,'registry_readonly_sha256':before,'source_grid_correction':'SHEET_CORRECTION.txt; corrected VFR image export','rows':rows}
  dest=ROOT/'SELECTED_MEDIA_AUDIT.json'
  with dest.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
  print(json.dumps({'status':'PASS','sha256':sha(dest),'seconds':out['seconds'],'rows':[{k:r[k] for k in ('id','clip_sha256','grid_sha256','decoded_frames')} for r in rows]}))
 return 0
if __name__=='__main__':raise SystemExit(main())

