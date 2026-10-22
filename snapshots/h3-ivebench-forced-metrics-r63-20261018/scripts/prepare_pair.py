"""Release one real R63 Native/forced pair to unchanged IVEBench valid-time inputs."""
import argparse,subprocess,sys,time
from pathlib import Path
from common import *
sys.path.insert(0,str(RUNTIME/'metric_runtime'))
import ive_mf_adapter as official

def validate_gate(g,source,count):
 if g.get('schema')!='r63-paired-runtime-gate-v1' or g.get('passed') is not True or g.get('source_id')!=source or g.get('prompt_version')!='P0':raise ValueError('R63 actual pair gate differs')
 for key in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal']:
  if g.get('checks',{}).get(key) is not True:raise ValueError('R63 paired condition/noise/prefix failed: '+key)
 if set(g.get('runs',{}))!={'native','forced'}:raise ValueError('both actual methods required')
 for method,r in g['runs'].items():
  if r.get('run_id')!='r63_'+source+'_seed2026101701_'+method or r.get('valid_frames')!=count or r.get('NFE')!=20 or r.get('routed_blocks')!=(0 if method=='native' else 450):raise ValueError('actual run/validtime/NFE/routing differs')
  if not isinstance(r.get('video'),dict) or set(('file','sha256'))-r['video'].keys():raise ValueError('actual video binding required')
 return g

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',choices=PAIRS,required=True);ap.add_argument('--producer',type=Path,required=True);ap.add_argument('--ffmpeg',default='/usr/bin/ffmpeg');ap.add_argument('--ffprobe',default='/usr/bin/ffprobe');a=ap.parse_args()
 verify_runtime();root=a.producer.resolve();selection=read(SELECTION);e=next(c for c in selection['pairs'] if c['pair_id']==a.source);count=e['input_protocol']['effective_frame_count']
 gatepath=root/'analysis/postrun'/a.source/'PAIR_RUNTIME_GATE.json';gate=validate_gate(read(gatepath),a.source,count)
 out=ROOT/'prepared'/a.source
 if (out/'METRIC_INPUTS.json').exists():raise FileExistsError('preserve prepared inputs; inspect prior receipt')
 with cpu_lock():
  started=time.monotonic();out.mkdir(exist_ok=True)
  row={'pair_id':a.source,'source_original':bound(root/'inputs'/(a.source+'_original.mp4')),'source_prepared_video':bound(root/'inputs'/(a.source+'_video.mp4')),'source_preparation_record':bound(root/'inputs'/(a.source+'_provenance.json')),'source_score_video':bound(ROOT/'inputs/source_scores'/a.source/'source_score.mp4'),'score_frame_indices':list(range(count)),'input_to_original_frame':e['input_protocol']['input_to_original_frame'],'edited':{}}
  official.validate_source_row(row,e,a.ffprobe,a.ffmpeg)
  source_report=read(ROOT/'tracks/source'/a.source/'REPORT.json')
  if source_report['source_score_sha256']!=row['source_score_video']['sha256'] or source_report['source_prepared_sha256']!=row['source_prepared_video']['sha256']:raise ValueError('cached source tracking does not bind current source')
  for method in ('native','forced'):
   run=gate['runs'][method];video=official.bound_file(run['video']);history=root/'logs'/(run['run_id']+'_history.json');job=root/'logs'/(run['run_id']+'_job.json');h=read(history);j=read(job)
   if not video.resolve().is_relative_to(root/'output'):raise ValueError('video outside current producer output')
   if h.get('status',{}).get('completed') is not True or h['status']['status_str']!='success' or j.get('status')!='success':raise ValueError('actual job/history incomplete')
   official.validate_full_view(official.media_info(video,a.ffprobe))
   score=out/(method+'_score.mp4');tmp=out/(method+'_score.partial.mp4')
   command=[a.ffmpeg,'-v','error','-nostdin','-n','-threads','2','-i',str(video),'-an','-vf',f'crop=1280:720:16:8,trim=end_frame={count},setsar=1','-vsync','0','-c:v','libx264','-preset','fast','-crf','0','-pix_fmt','yuv420p','-threads','2',str(tmp)]
   subprocess.run(command,check=True,timeout=180);tmp.rename(score)
   row['edited'][method]={'score_video':bound(score),'full_video':bound(video),'generation_record':bound(history),'release_record':bound(gatepath)}
   official.validate_edited_entry(row['edited'][method],count,a.ffprobe,a.ffmpeg)
  row['producer_runtime_gate']=bound(gatepath);row['runtime_freeze_sha256']=sha(ROOT/'RUNTIME_FREEZE.json')
  save(out/'METRIC_INPUTS.json',row)
  save(out/'PREPARATION.json',{'passed':True,'pair_id':a.source,'fixed_denominator':5,'effective_frames':count,'time_samples':'i/24 seconds; crop16,8,1280,720','metric_inputs':bound(out/'METRIC_INPUTS.json'),'source_cache_report':bound(ROOT/'tracks/source'/a.source/'REPORT.json'),'wall_seconds':time.monotonic()-started,'tracker_started':False})
  print(json.dumps({'prepared':str(out/'METRIC_INPUTS.json'),'effective_frames':count,'tracker_started':False}))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
