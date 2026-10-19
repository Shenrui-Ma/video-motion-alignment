"""Frozen two-video CPU-only pixel diagnostic. Never writes producer/legacy archives."""
import argparse,fcntl,hashlib,json,math,os,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(x,m):
 if not x:raise ValueError(m)
def save(p,a):
 with Path(p).open('x') as f:json.dump(a,f,indent=2,allow_nan=False);f.write('\n')
def stats(abs_sum,sq_sum,channels,pixels,changed_channels,changed_pixels,max_abs):
 mse=sq_sum/channels
 return {'MAE_0_255':abs_sum/channels,'RMSE_0_255':math.sqrt(mse),'PSNR_dB':None if mse==0 else 10*math.log10(255**2/mse),'PSNR_is_infinite':mse==0,'max_abs_0_255':max_abs,'different_channel_fraction':changed_channels/channels,'different_pixel_fraction_any_RGB':changed_pixels/pixels,'absolute_error_sum':abs_sum,'squared_error_sum':sq_sum,'channels':channels,'pixels':pixels,'different_channels':changed_channels,'different_pixels':changed_pixels}
def online_pending(p):
 for root in p['online_priority_roots']:
  for d in (Path(root)/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False

def main():
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);args=a.parse_args();p=read(HERE/'PROTOCOL.json');require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be hidden')
 for n,d in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/n)==d,'diagnostic freeze changed '+n)
 if online_pending(p):raise BlockingIOError('online priority')
 with Path(p['remote_cpu_lock']).open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if online_pending(p):raise BlockingIOError('online priority')
  started=time.monotonic();e=read(HERE/'INPUT_EVIDENCE.json');old=Path(e['partial_final_root'])
  def check_inputs():
   require({str(f.relative_to(old)) for f in old.rglob('*') if f.is_file()}==set(e['partial_inventory']),'partial exact inventory changed')
   for rel,d in e['partial_inventory'].items():require(sha(old/rel)==d['sha256'] and (old/rel).stat().st_size==d['bytes'],'partial changed '+rel)
   for row in e['videos'].values():require(sha(row['path'])==row['sha256'],'video changed')
  check_inputs()
  import cv2,numpy as np
  cv2.setNumThreads(1);caps={};probes={};rows=[];total=[0,0,0,0,0,0,0]
  try:
   for name,row in e['videos'].items():
    path=row['path'];probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_format','-show_frames','-of','json',path],timeout=40));probes[name]=probe
    require(len(probe['frames'])==141 and all(abs(float(v['best_effort_timestamp_time'])-i/24)<1e-6 for i,v in enumerate(probe['frames'])),'actual141 physical PTS differs')
    cap=cv2.VideoCapture(path,cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);require(cap.isOpened(),'video open failed');caps[name]=cap
    require([int(cap.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT,cv2.CAP_PROP_FRAME_COUNT)]==[1312,736,141] and cap.get(cv2.CAP_PROP_FPS)==24,'actual video geometry')
   for i in range(141):
    rgb={}
    for name,cap in caps.items():
     ok,bgr=cap.read();require(ok,'earlyEOF');rgb[name]=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);require(hashlib.sha256(rgb[name].tobytes()).hexdigest()==e['existing_pixels']['RGB_frame_sha256'][name][i],'decodedRGB differs from failed-final evidence')
    d=rgb['AUTO'].astype(np.int16)-rgb['normal_native'].astype(np.int16);ad=np.abs(d);s=[int(ad.sum(dtype=np.int64)),int((d.astype(np.int32)**2).sum(dtype=np.int64)),int(d.size),int(d.shape[0]*d.shape[1]),int(np.count_nonzero(d)),int(np.count_nonzero(np.any(d!=0,axis=2))),int(ad.max())]
    rows.append({'frame':i,'physical_time_seconds':i/24,**stats(*s)})
    for j in range(6):total[j]+=s[j]
    total[6]=max(total[6],s[6])
   require(all(not c.read()[0] for c in caps.values()),'extra frame')
  finally:
   for c in caps.values():c.release()
  check_inputs();logs={}
  for name,r in p['producer_roots'].items():
   f=Path(r)/'logs/comfyui.log';lines=f.read_text().splitlines();logs[name]={'file':str(f),'sha256':sha(f),'relevant_lines':[{'line':i+1,'text':s} for i,s in enumerate(lines) if any(k in s.lower() for k in ('vae dtype','vae load','model weight dtype','requested to load','out of memory','tiled'))]}
  result={'scope':p['scope'],'passed_input_integrity':True,'RGB_equality':total[5]==0,'aggregate':stats(*total),'frames':rows,'fixed_frame_summaries':[rows[i] for i in p['fixed_frames']],'probe':probes,'logs':logs,'video_inputs':e['videos'],'input_evidence_sha256':sha(HERE/'INPUT_EVIDENCE.json'),'protocol_sha256':sha(HERE/'PROTOCOL.json'),'runtime':{'opencv':cv2.__version__,'numpy':np.__version__,'threads':1,'CUDA_VISIBLE_DEVICES':'','elapsed_seconds':time.monotonic()-started},'attribution':'Difference measured after MP4 decoding only. Small errors cannot identify encoder versus VAE origin; pre-encode float/RGB not archived for both actual final outputs.'}
  save(args.output,result);print(json.dumps({'output':args.output,'sha256':sha(args.output),'aggregate':result['aggregate'],'elapsed_seconds':result['runtime']['elapsed_seconds']}))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
