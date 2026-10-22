from pathlib import Path
import os,json,sys,hashlib,subprocess,time
R=Path(__file__).resolve().parent
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
p=json.loads((R/'PROTOCOL.json').read_text());start=time.monotonic()
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
for rel,h in p['files'].items():assert sha(R/rel)==h
for k in ['source_video','native_video']:assert sha(p[k]['file'])==p[k]['sha256']
cmd=[sys.executable,str(R/'scripts/pose_probe.py'),'--video',p['source_video']['file'],'--video',p['native_video']['file'],'--output-dir',str(R/'poses'),'--threads','2','--overlay-frame','95','--overlay-frame','112']
subprocess.run(cmd,check=True)
src=R/'poses'/(Path(p['source_video']['file']).stem+'.pose.json');dst=R/'poses'/(Path(p['native_video']['file']).stem+'.pose.json')
subprocess.run([sys.executable,str(R/'scripts/scan_current_pose.py'),'--source',str(src),'--pose',str(dst),'--index','0','--output',str(R/'SCAN.json'),'--geometry-case',str(R/'CASE.json')],check=True)
sys.path.insert(0,str(R/'scripts'));sys.path.insert(0,str(R/'extensions'))
from H3AutomaticWindowRouter.automatic_window_policy import candidate,components
scan=json.loads((R/'SCAN.json').read_text());eligible=[v for row in scan['windows']if (v:=candidate(row)) is not None]
coverage={}
for role,path in [('source',src),('native',dst)]:
 raw=json.loads(path.read_text());records=raw['frames'][:144];coverage[role]={'pose_sha256':sha(path),'processed_frames':len(raw['frames']),'valid_frames':144,'missing_selected':sum(r['selected_person'] is None for r in records),'joints':{},'statistics':raw['statistics']}
 for j,name in [(5,'left_shoulder'),(6,'right_shoulder'),(7,'left_elbow'),(8,'right_elbow'),(9,'left_wrist'),(10,'right_wrist')]:
  values={}
  for threshold in [.3,.5]:
   good=[];visible=[]
   for row in records:
    sel=row['selected_person'];q=row['persons'][sel] if sel is not None else None
    conf=q is not None and q['coco17_score'][j]>=threshold;xy=q['coco17_xy'][j]if q else [-1,-1]
    good.append(bool(conf));visible.append(bool(conf and 16<=xy[0]<1296 and 8<=xy[1]<728))
   values[str(threshold)]={'confidence_frames':sum(good),'confidence_and_in_content_frames':sum(visible),'denominator':144,'late_phase_confidence_and_in_content_frames':sum(visible[80:128]),'late_phase_denominator':48}
  coverage[role]['joints'][name]=values
summary={'passed_execution':True,'protocol_sha256':sha(R/'PROTOCOL.json'),'scan_sha256':sha(R/'SCAN.json'),'source_pose':str(src),'native_pose':str(dst),'coverage':coverage,'rows':len(scan['windows']),'baseline_counts':{k:sum(x['baseline']==k for x in scan['windows'])for k in sorted({x['baseline']for x in scan['windows']})},'qualifying_rows':eligible,'qualifying_groups':components(scan['windows']),'withdrawal_overlapping_qualifying_rows':[x for x in eligible if x['window'][0]<=98 and x['window'][1]>=95],'temporal_persistence_tested':False,'actual_online_triggered':False,'CPU_wall_seconds':time.monotonic()-start,'GPU_started':False}
(R/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print({'summary_sha256':sha(R/'SUMMARY.json'),'rows':summary['rows'],'qualifying':len(eligible),'wall':summary['CPU_wall_seconds']})
