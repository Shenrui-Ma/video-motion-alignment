"""Bounded CPU-only source processing, before all generated outcomes."""
import argparse,fcntl,hashlib,json,shutil,signal,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
SCOPE=Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/new_source_candidates_20261017')
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
CASES={'10264579':(366,'Sam Altman','/Users/researcher/DevProjects/h3-timing-source51765-native-r43-20261017/inputs/source_51765_portrait.jpg','4231440d7d8c8305b5f1bdd497ad699fee30e07443ba8ee681cedd19c1a7da42'),'6980766':(192,'Elon Musk','/Users/researcher/DevProjects/h3-timing-source28289-native-r42-20261017/inputs/source_28289_portrait.jpg','8aab8262f1da5ae98dec83f7ed677c1aed5164130ddf73d51d80ad922ee40b45')}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('id',choices=CASES);a=ap.parse_args()
 with LOCK.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('BUSY');return 75
  signal.alarm(120);t=time.perf_counter()
  selected=next(x for x in json.loads((SCOPE/'SOURCE_SELECTION.json').read_text())['selected'] if x['id']==a.id)
  start,identity,portrait,portrait_sha=CASES[a.id]
  source=Path(selected['original']);assert sha(source)==selected['original_sha256']
  out=ROOT/'inputs'/f'source_{a.id}_video.mp4';assert not out.exists()
  vf=f'fps=24:round=near,trim=start_frame={start}:end_frame={start+141},setpts=PTS-STARTPTS,scale=-2:736:flags=lanczos,crop=1312:736:42:0,setsar=1'
  cmd=['/opt/homebrew/bin/ffmpeg','-nostdin','-v','error','-threads','4','-i',str(source),'-vf',vf,'-an','-r','24','-fps_mode','cfr','-c:v','libx264','-crf','18','-preset','fast','-threads','4','-filter_threads','4','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
  subprocess.run(cmd,check=True,timeout=90)
  dest=ROOT/'inputs'/f'source_{a.id}_portrait.jpg'
  assert sha(portrait)==portrait_sha;shutil.copyfile(portrait,dest);assert sha(dest)==portrait_sha
  probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-threads','4','-show_frames','-show_streams','-show_format','-of','json',str(out)],timeout=30))
  frames=probe['frames'];assert len(frames)==141
  assert [int(f['best_effort_timestamp']) for f in frames]==[512*i for i in range(141)]
  assert all((f['width'],f['height'])==(1312,736) for f in frames)
  assert probe['streams'][0]['avg_frame_rate']=='24/1'
  (ROOT/'design'/f'INPUT_PROBE_{a.id}.json').write_text(json.dumps(probe,indent=2)+'\n')
  gridfolder=ROOT/'design'/f'grid_{a.id}';gridfolder.mkdir()
  subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','4','-i',str(out),'-vf','select=not(mod(n\\,6)),scale=328:184','-filter_threads','4','-fps_mode','vfr','-frames:v','24',str(gridfolder/'f%02d.jpg')],check=True,timeout=30)
  paths=sorted(gridfolder.glob('f*.jpg'));assert len(paths)==24
  canvas=Image.new('RGB',(1312,6*208),'black');draw=ImageDraw.Draw(canvas)
  for i,p in enumerate(paths):
   x=i%4*328;y=i//4*208;canvas.paste(Image.open(p),(x,y+24));draw.text((x+4,y+5),f'{a.id} frame {i*6:03d} | {i*.25:.2f}s',fill='white')
  canvas.save(ROOT/'design'/f'SOURCE_GRID_{a.id}.jpg',quality=92)
  provenance={'source_id':a.id,'source_selected_before_inference':selected,'command':cmd,'source_original_sha256':sha(source),'video_sha256':sha(out),'portrait_source':portrait,'portrait_sha256':portrait_sha,'identity':identity,'seed':2026101701,'normalized_24fps_source_indices_inclusive':[start,start+140],'geometry':{'original':[4096,2160],'scale_expression':'scale=-2:736:flags=lanczos','scaled':[1396,736],'crop':[42,0,1312,736],'rounding':'proportional width rounded to even integer; original aspect preserved to integer precision','full_height_preserved':True,'left_right_scaled_pixels_removed_each':42},'frames':141,'fps':24,'duration_s':141/24,'integer_pts_stride':512,'elapsed_seconds':time.perf_counter()-t,'inference_observed':False}
  (ROOT/'inputs'/f'source_{a.id}_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'id':a.id,'sha256':sha(out),'seconds':provenance['elapsed_seconds'],'frames':141,'grid':str(ROOT/'design'/f'SOURCE_GRID_{a.id}.jpg')}))
 return 0
if __name__=='__main__':raise SystemExit(main())

