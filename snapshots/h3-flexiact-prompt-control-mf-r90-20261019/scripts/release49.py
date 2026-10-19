"""Publish an exact sampled49-frame scoring copy; original158 output is preserved."""
import argparse,hashlib,json,shutil,subprocess
from fractions import Fraction
from pathlib import Path
INDICES=tuple(range(0,147,3))
def validate_probe(value,frames,fps):
 st=value['streams'];fr=value['frames']
 if len(st)!=1 or len(fr)!=frames or (st[0]['width'],st[0]['height'])!=(1152,768) or Fraction(st[0]['avg_frame_rate'])!=fps:raise ValueError('wrong video geometry/grid')
 for i,f in enumerate(fr):
  t=float(f['best_effort_timestamp_time'])
  if not abs(t-i/fps)<1e-6:raise ValueError('nonfinite or shifted source time')
def run(source,destination):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if source==destination or destination.exists():raise ValueError('refusing overwrite')
 ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe')
 def probe(p):return json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)],text=True))
 def hashes(p):return [x.split(',')[-1].strip() for x in subprocess.check_output([ffmpeg,'-v','error','-threads','2','-i',str(p),'-an','-pix_fmt','yuv420p','-threads','2','-f','framemd5','-'],text=True).splitlines() if x and not x.startswith('#')]
 validate_probe(probe(source),158,24);before=hashes(source)
 cmd=[ffmpeg,'-v','error','-threads','2','-i',str(source),'-an','-vf',"select='lt(n,147)*not(mod(n,3))',setpts=N/(8*TB)",'-r','8','-c:v','libx264','-crf','0','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(destination)]
 subprocess.run(cmd,check=True,timeout=60);validate_probe(probe(destination),49,8);after=hashes(destination)
 if after!=[before[i] for i in INDICES]:raise ValueError('decoded selected frames differ')
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 rec={'source':str(source),'source_sha256':sha(source),'destination':str(destination),'destination_sha256':sha(destination),'input_indices':INDICES,'physical_seconds':[i/8 for i in range(49)],'terminal_padding_excluded':True,'decoded_frame_md5_equal':True,'command':cmd}
 destination.with_suffix('.mapping.json').write_text(json.dumps(rec,indent=2)+'\n');return rec
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();print(json.dumps(run(a.source,a.destination)))
