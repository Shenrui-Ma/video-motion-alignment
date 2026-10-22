"""Prepare uploaded official sources with exact inherited frame mapping; CPU only.
Usage: python3 extension2/prepare_remote_inputs.py --root /path/to/host9a
This never edits a queue, graph, catalog, service or GPU process.
"""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def run(cmd,**kw):return subprocess.run(cmd,check=True,capture_output=True,timeout=300,**kw)
def decode(p,width,height,transform=None):
 cmd=['ffmpeg','-v','error','-threads','2','-i',str(p),'-an']
 if transform:cmd+=['-vf',transform]
 cmd+=['-vsync','0','-pix_fmt','yuv420p','-threads','2','-f','rawvideo','-']
 raw=run(cmd).stdout;size=width*height*3//2
 if len(raw)%size:raise ValueError('Partial decoded frame')
 return raw,[hashlib.md5(raw[i:i+size]).hexdigest() for i in range(0,len(raw),size)]
def prepare(source,dest,mapping,width,height,transform):
 size=width*height*3//2
 raw,hashes=decode(source,width,height,transform)
 if max(mapping)>=len(hashes) or min(mapping)<0:raise ValueError('Source mapping outside decoded range')
 temp=dest.with_name(dest.stem+'.preparing.mp4')
 if dest.exists() or temp.exists():raise FileExistsError(str(dest))
 selected=b''.join(raw[i*size:(i+1)*size] for i in mapping); del raw
 run(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','yuv420p','-s:v',f'{width}x{height}','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','0','-preset','fast','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)],input=selected);del selected
 raw,actual=decode(temp,width,height);del raw
 expected=[hashes[i] for i in mapping]
 if actual!=expected:raise ValueError('Decoded pixels differ from explicit source mapping')
 p=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames:frame=best_effort_timestamp_time','-show_frames','-of','json',str(temp)]).stdout)
 if len(p['frames'])!=len(mapping) or any(abs(float(f['best_effort_timestamp_time'])-i/24)>1e-6 for i,f in enumerate(p['frames'])):raise ValueError('Frame count or 24fps timestamps mismatch')
 temp.replace(dest)
 return {'sha256':sha(dest),'bytes':dest.stat().st_size,'ffprobe':p['streams'][0],'decoded_pixel_mapping_exact':True,'original_transformed_frame_md5':hashes,'input_frame_md5':actual,'input_to_original_frame':mapping}
def self_test():
 with tempfile.TemporaryDirectory(prefix='prepare-test-',dir=Path(__file__).resolve().parent) as temp:
  root=Path(temp);source=root/'source.mp4';dest=root/'mapped.mp4'
  run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x32:rate=12:duration=0.5','-c:v','libx264','-crf','0',str(source)])
  result=prepare(source,dest,[0,1,1,2,3,4,5,5],64,32,'setsar=1')
  assert result['decoded_pixel_mapping_exact'] and len(result['input_frame_md5'])==8
  print('Self-test passed: exact duplicated frame mapping, lossless encode and 24fps timestamps')
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path);p.add_argument('--self-test',action='store_true');args=p.parse_args()
 if args.self_test:self_test();return
 if not args.root:p.error('--root required')
 root=args.root.resolve(); pack=root/'extension2';catalog=read(pack/'catalog.json');transfers=read(pack/'assets_to_transfer.json');assets={t['task_id']:t for t in transfers['files']};receipts=[]
 (root/'input').mkdir(parents=True,exist_ok=True);(pack/'receipts').mkdir(exist_ok=True)
 for t in catalog['tasks']:
  tid=t['task_id'];asset=assets[tid];dest=root/'input'/t['graph_input_names']['video'];receipt=pack/'receipts'/f'{tid}.json'
  if t['input_status']=='existing_prepared':
   if sha(dest)!=asset['sha256']:raise ValueError('Prepared source hash mismatch '+tid)
   receipts.append({'task_id':tid,'path':str(dest),'sha256':sha(dest),'verified_existing_prepared':True});continue
  source=pack/'sources'/f'{tid}.mp4'
  if sha(source)!=asset['sha256']:raise ValueError('Official original hash mismatch '+tid)
  if dest.exists():
   recorded=read(receipt)
   if sha(dest)!=recorded['sha256'] or recorded['input_to_original_frame']!=t['input_to_original_frame']:raise ValueError('Existing prepared input mismatch '+tid)
   receipts.append(recorded);continue
  g=t['geometry'];result=prepare(source,dest,t['input_to_original_frame'],g['width'],g['height'],t['preparation_transform'])
  result.update(task_id=tid,path=str(dest),source_sha256=sha(source),valid_frames=t['valid_frames'],geometry=g,evaluation_crop_xywh=t['evaluation_crop_xywh'],original_pts_rational=t['original_pts_rational'],padding_indices=list(range(t['valid_frames'],g['frames'])))
  receipt.write_text(json.dumps(result,indent=2)+'\n');receipts.append(result);print(tid,'verified',result['sha256'],flush=True)
 ready={'ready':True,'count':len(receipts),'inputs':receipts}
 (pack/'input_ready.json').write_text(json.dumps(ready,indent=2)+'\n');print('All',len(receipts),'inputs verified. Queue remains unchanged.')
if __name__=='__main__':main()
