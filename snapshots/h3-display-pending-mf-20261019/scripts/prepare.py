"""Bind all missing displayed media and physical timestamps; CPU preparation only."""
from pathlib import Path
import os,json,hashlib,subprocess,shutil,importlib.util,time
R=Path(__file__).resolve().parents[1];D=R.parent
A=D/'h3-ive-long0174-correspondence-metrics-r115-20261019/audit/latest_display_evidence_20261019'
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def link(src,dst):
 src=Path(src);dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 assert sha(src)==sha(dst)
def media(p):
 d=json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)],text=True));s=d['streams'][0];return dict(width=s['width'],height=s['height'],fps=s['avg_frame_rate'],frames=len(d['frames']),pts=[float(x['best_effort_timestamp_time']) for x in d['frames']])
def hashes(p,vf=None):
 c=[FF,'-v','error','-threads','2','-i',str(p),'-an']
 if vf:c+=['-vf',vf]
 c+=['-vsync','0','-pix_fmt','yuv420p','-threads','2','-f','framemd5','-'];return [l.split(',')[-1].strip() for l in subprocess.check_output(c,text=True).splitlines() if l and not l.startswith('#')]
def crop(p,o,n):
 vf=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
 if not o.exists():subprocess.run([FF,'-v','error','-nostdin','-n','-threads','2','-i',str(p),'-an','-vf',vf,'-vsync','0','-c:v','libx264','-preset','fast','-crf','0','-pix_fmt','yuv420p','-threads','2',str(o)],check=True)
 assert hashes(p,vf)==hashes(o)
 return hashes(o)
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 rows=[]
 for name in ('flexiact','ivebench'):rows+=read(D/f'h3-benchmark-all-results-showcase-20261018/inventory/{name}.json')['items']
 inv={x['id']:x for x in rows};pending=read(A/'SCORE_REUSE_VERIFIED.json')['remaining_missing']
 for name,p in [('ive',D/'h3-ive-followup-quantitative-r97-r99-r100-20261019/runtime'),('flex',D/'h3-flexiact-character-repair-mf-r98-20261019/runtime/official_metric')]:
  dest=R/'runtime'/name
  if not dest.exists():shutil.copytree(p,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc','weights','inputs','SOURCE_INPUTS.json'))
  frozen={str(f.relative_to(dest)):sha(f) for f in dest.rglob('*') if f.is_file()}
  assert all(sha(p/n)==h for n,h in frozen.items());save(R/'configs'/f'{name}_NUMERIC.json',dict(source=str(p),files=frozen))
 release=load('unchanged_release',D/'h3-flexiact-character-repair-mf-r98-20261019/runtime/release/release49.py')
 report_files=[];scorefiles=[]
 for base in D.iterdir():
  if base.is_dir() and base.name.startswith('h3-') and any(t in base.name for t in ['metric','quantitative','evaluation']):
   report_files.extend(base.rglob('REPORT.json'));scorefiles.extend(base.rglob('source_score.mp4'))
 reports=[]
 for p in report_files:
  try:
   q=read(p)
   if q.get('passed'):reports.append((p,q))
  except (ValueError,OSError):pass
 scoreindex={sha(p):p for p in scorefiles};groups={};jobs=[];target_index={}
 for x in pending:
  row=inv[x['id']];bench=row['benchmark'];n=row['valid_frames'];full=Path(x['media']);assert sha(full)==x['media_sha256'];src=Path(row['reference_video_path']);assert sha(src)==x['source_sha256']
  fi=media(full);si=media(src);assert fi['fps']=='24/1' and si['fps']=='24/1';assert fi['frames']>=n and si['frames']>=n
  assert all(abs(t-i/24)<1e-6 for i,t in enumerate(fi['pts']));assert all(abs(t-i/24)<1e-6 for i,t in enumerate(si['pts']))
  official=None;prov=None
  if bench=='FlexiAct':
   assert n==147 and fi['frames']==158 and (fi['width'],fi['height'])==(1152,768)
   pp=src.with_name(src.name.replace('_video.mp4','_provenance.json'));prov=read(pp);o=prov.get('official_source',prov.get('original_source')) or dict(path=str(D/'h3-flexiact-expanded-selection-20261018/official_assets/benchmark/reference_videos/human'/f"{row['source_id']}.mp4"),sha256=prov['source_original_sha256']);official=Path(o.get('local_path',o.get('path')));assert sha(official)==prov['source_original_sha256']==o['sha256'];oi=media(official);assert oi['frames']==49 and all(abs(t-i/8)<1e-6 for i,t in enumerate(oi['pts']));source_sha=sha(official);count=49;fps=8
  else:
   assert (fi['width'],fi['height'])==(1312,736) and (si['width'],si['height'])==(1312,736);source_sha=sha(src);count=n;fps=24
  key=bench.lower()+'_'+row['source_id']+'_'+hashlib.sha256((source_sha+str(count)).encode()).hexdigest()[:10]
  if key not in groups:
   b=R/'cases'/key;b.mkdir(parents=True,exist_ok=True);link(src,b/'source_full.mp4')
   g=dict(key=key,benchmark=bench,source_id=row['source_id'],valid_frames=n,evaluation_frames=count,evaluation_fps=fps,source_full='source_full.mp4',source_full_sha256=sha(src),source_full_properties=si,original_source=None,targets=[],source_cache=None)
   if bench=='FlexiAct':
    link(official,b/'source_score.mp4');link(pp,b/'SOURCE_PROVENANCE.json');g['original_source']=dict(file=str(official),sha256=source_sha);g['canonical_id']='human/'+row['source_id']+'/000';g['source_frame_md5']=hashes(b/'source_score.mp4')
   else:g['source_frame_md5']=crop(src,b/'source_score.mp4',n);g['canonical_id']=row['source_id']
   g['source_score_sha256']=sha(b/'source_score.mp4')
   for rp,q in reports:
    tp=rp.parent/('tracks.pt' if bench=='FlexiAct' else 'tracks.npz')
    if not tp.is_file() or sha(tp)!=q.get('tracks_sha256'):continue
    if bench=='FlexiAct':
     ok=q.get('case',{}).get('role')=='reference' and q['case'].get('sha256')==source_sha and q['case'].get('id')==g['canonical_id'] and q.get('checkpoint_sha256')=='dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3' and q.get('grid_size')==55 and q.get('mask')is None and q.get('tracks_shape')==[3025,49,2]
     if ok:ok=q.get('metric_functions_sha256')==sha(R/'runtime/flex/METRIC_FUNCTIONS.json') and q.get('vendor_manifest_sha256')==sha(R/'runtime/flex/VENDOR.json') and [float(z['best_effort_timestamp_time']) for z in q['timebase']['frames']]==[i/8 for i in range(49)]
    else:
     ok=q.get('method')=='source' and q.get('source_prepared_sha256')==source_sha and q.get('effective_frame_count')==n and q.get('score_frame_indices')==list(range(n)) and q.get('decoded_frame_md5')==g['source_frame_md5'] and q.get('tracker')==dict(grid_size=10,grid_query_frame=0,backward_tracking=False,offline=True,window_len=60) and q.get('checkpoint_sha256')=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
     if ok and q.get('source_score_sha256')!=g['source_score_sha256']:
      old=scoreindex.get(q['source_score_sha256']);ok=old is not None and hashes(old)==g['source_frame_md5']
      if ok:
       (b/'source_score.mp4').unlink();link(old,b/'source_score.mp4');g['source_score_sha256']=sha(b/'source_score.mp4')
    if ok:
     link(rp,b/'tracks/source/REPORT.json');link(tp,b/'tracks/source'/tp.name);g['source_cache']=dict(report_file=str(rp),report_sha256=sha(rp),tracks_file=str(tp),tracks_sha256=sha(tp),runtime_provenance={k:q.get(k) for k in ['torch_version','cuda_version','admission_before_cuda']});g['selection_sha256']=q.get('selection_sha256');break
   if not g['source_cache']:jobs.append(dict(case=key,role='source'))
   groups[key]=g
  g=groups[key];b=R/'cases'/key;tkey=x['media_sha256']+'|'+key
  if tkey in target_index:
   target_index[tkey]['inventory_bindings'].append(dict(id=x['id'],field=x['field']));continue
  role='target_'+str(len(g['targets'])).zfill(2);tb=b/role;tb.mkdir(exist_ok=True);link(full,tb/'full.mp4')
  if bench=='FlexiAct':
   out=tb/'score.mp4'
   if not out.exists():release.run(tb/'full.mp4',out)
   md=hashes(out);idx=list(range(0,147,3));assert md==hashes(full,"select='not(mod(n,3))',trim=end_frame=49,setpts=N/(8*TB)")
  else:md=crop(full,tb/'score.mp4',n);idx=list(range(n))
  t=dict(role=role,full_file=role+'/full.mp4',full_sha256=sha(full),full_properties=fi,score_file=role+'/score.mp4',score_sha256=sha(tb/'score.mp4'),score_frame_md5=md,evaluation_indices=idx,inventory_bindings=[dict(id=x['id'],field=x['field'])],original_media=str(full),source_provenance_paths=row.get('evidence_paths',[]))
  g['targets'].append(t);target_index[tkey]=t;jobs.append(dict(case=key,role=role));print('PREPARED',x['id'],x['field'],flush=True)
 for k,g in groups.items():
  if not g.get('selection_sha256'):g['selection_sha256']=hashlib.sha256((k+g['source_score_sha256']).encode()).hexdigest()
  save(R/'cases'/k/'INPUTS.json',g)
 plan=dict(schema='all-display-pending-official-mf-v1',inventory_inputs=[dict(file=str(invpath),sha256=sha(invpath)) for invpath in [D/'h3-benchmark-all-results-showcase-20261018/inventory/flexiact.json',D/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json']],missing_list_binding=dict(file=str(A/'SCORE_REUSE_VERIFIED.json'),sha256=sha(A/'SCORE_REUSE_VERIFIED.json')),groups=list(groups),jobs=jobs,requested_fields=len(pending),unique_targets=len(target_index),source_cache_count=sum(g['source_cache']is not None for g in groups.values()),no_GPU=True)
 save(R/'configs/PLAN.json',plan);print(json.dumps({k:v for k,v in plan.items() if k not in ['jobs','groups','inventory_inputs','missing_list_binding']}))
if __name__=='__main__':main()
