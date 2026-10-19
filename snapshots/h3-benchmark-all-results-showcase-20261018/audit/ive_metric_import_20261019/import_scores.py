"""Import existing frozen official scores; no tracker or score computation."""
import argparse,copy,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DEV=ROOT.parent
AUDIT=Path(__file__).resolve().parent
OFFICIAL='2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
CHECKPOINT='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
TRACKER={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}
PROTOCOL='IVEBench official MF; commit '+OFFICIAL+'; CoTracker3 offline, grid10, window60'
NAMES={63:'ivebench_forced_metrics',64:'ivebench_heldout_metrics',69:'ivebench_remaining_metrics',73:'ivebench_expanded_metrics'}
LOCALS={63:'h3-ivebench-forced-metrics',64:'h3-ivebench-heldout-metrics',69:'h3-ivebench-remaining-metrics',73:'h3-ivebench-expanded-metrics'}
MAP={}
for k,name in NAMES.items():MAP[('/data5' if k in (63,73) else '/data3')+'/researcher/h3_runs/'+name+f'_r{k}_20261018']=DEV/(LOCALS[k]+f'-r{k}-20261018')
for k,name in [(54,'native'),(55,'auto')]:MAP[f'/data3/researcher/h3_runs/timing_ivebench_{name}_r{k}_20261017']=DEV/f'h3-timing-ivebench-{name}-r{k}-20261017'
MAP['/data5/researcher/h3_runs/timing_ivebench_forced_r63_20261018']=DEV/'h3-timing-ivebench-forced-r63-20261018'
MAP['/data3/researcher/h3_runs/ivebench_official_metric_20261017']=DEV/'h3-timing-ivebench-native-r54-20261017/analysis/postrun/mf_execution/captured/ivebench_official_metric_20261017'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def req(ok,msg):
 if not ok:raise ValueError(msg)
def local(remote):
 for root,p in sorted(MAP.items(),key=lambda x:-len(x[0])):
  if str(remote).startswith(root+'/'):
   candidate=p/str(remote)[len(root)+1:];cached=AUDIT/'collected_json'/str(remote).lstrip('/')
   return candidate if candidate.is_file() or not cached.is_file() else cached
 raise ValueError('unmapped path '+str(remote))
class Evidence:
 def __init__(self):self.paths={}
 def load(self,p,digest=None):
  p=Path(p);req(p.is_file(),'missing JSON '+str(p));s=sha(p);req(digest is None or s==digest,'JSON SHA differs '+str(p));self.paths[str(p)]=s;return read(p)
 def bound(self,row):return self.load(local(row['file']),row['sha256'])
 def media(self,item,field,expected):
  req(item.get(field) is not None,'missing media field '+field);req(sha(item[field])==expected==item['media_sha256'][field],'full media bytes differ '+field)
def validate_reports(e,score,manifest,item,method):
 req(score['schema']=='h3-ivebench-official-mf-cached-result-v1' and score['pair_id']==item['source_id'] and score['method']==method,'score role differs')
 req(score['official_vendor']['commit']==OFFICIAL and score['checkpoint_sha256']==CHECKPOINT and score['cuda_initialized'] is False,'official runtime differs')
 req(isinstance(score['motion_fidelity'],(float,int)) and math.isfinite(score['motion_fidelity']),'invalid numeric score')
 reports=[]
 for role in ('source','target'):
  report=e.bound(score[role+'_report']);reports.append(report)
  req(report['passed'] is True and report['pair_id']==item['source_id'],'tracker did not pass')
  req(report['tracks_sha256']==score[role+'_tracks_sha256'],'track receipt differs')
  req(report['vendor']==score['official_vendor'] and report['checkpoint_sha256']==CHECKPOINT and report['tracker']==TRACKER,'tracker protocol differs')
  req(report['source_prepared_sha256']==manifest['source_prepared_video']['sha256'] and report['source_score_sha256']==manifest['source_score_video']['sha256'],'tracker source differs')
  req(report['effective_frame_count']==item['valid_frames'] and report['score_frame_indices']==list(range(item['valid_frames'])),'tracker physical support differs')
  tracked=e.bound(report['input_manifest'])
  if 'pairs' in tracked:
   rows=[x for x in tracked['pairs'] if x['pair_id']==item['source_id']];req(len(rows)==1,'source manifest duplicate/missing');tracked=rows[0]
  req(tracked['source_prepared_video']['sha256']==manifest['source_prepared_video']['sha256'] and tracked['source_score_video']['sha256']==manifest['source_score_video']['sha256'],'tracked source manifest differs')
 source,target=reports
 req(source['method']=='source' and target['method']==method,'tracker role differs')
 req(target['score_video']==manifest['edited'][method]['score_video'],'target score media differs')
 req(source['score_video']['sha256']==manifest['source_score_video']['sha256'],'source score media differs')
 for key in ('torch_version','cuda_version','official_commit','tracker','checkpoint_sha256','effective_frame_count','score_frame_indices'):req(source[key]==target[key],'source/target runtime differs '+key)
 return float(score['motion_fidelity'])
def normal(item,k):
 p=DEV/(LOCALS[k]+f'-r{k}-20261018');source=item['source_id'];e=Evidence();m=e.load(p/'prepared'/source/'METRIC_INPUTS.json')
 gate=e.bound(m['producer_runtime_gate']);req(gate.get('passed') is True and all(x is True for x in gate['checks'].values()),'actual pair gate failed');req(gate['source_id']==source,'gate source differs')
 ref_sha=item['media_sha256']['reference_video_path'];req(ref_sha in [m['source_prepared_video']['sha256'],m['source_score_video']['sha256']],'reference source SHA differs');e.media(item,'reference_video_path',ref_sha);req(m['score_frame_indices']==list(range(item['valid_frames'])),'manifest physical support differs')
 scores={}
 for method,field in [('native','ordinary_video_path'),('forced','guided_video_path')]:
  target_sha=item['media_sha256'][field];req(target_sha in [m['edited'][method]['full_video']['sha256'],m['edited'][method]['score_video']['sha256']],'target media SHA differs');e.media(item,field,target_sha);req(gate['runs'][method]['video']['sha256']==m['edited'][method]['full_video']['sha256'] and gate['runs'][method]['valid_frames']==item['valid_frames'],'actual gate output/support differs')
  folder=p/'analysis/source_runtime_check/results' if k==63 else p/'results'/source
  candidates=sorted(folder.glob(method+'_source*_target*.json'));req(len(candidates)==1,'missing or ambiguous official score '+str(folder/method))
  result=e.load(candidates[0]);scores[method]=validate_reports(e,result,m,item,method)
 return scores['native'],scores['forced'],e.paths,'全点官方MF，逐源有效帧；衡量轨迹运动相似性，不等同动作时延或编辑任务完成度。'
def reused(item):
 e=Evidence();s=item['source_id'];base=DEV/'h3-timing-ivebench-auto-r55-20261017/analysis/postrun/audit/media_identity'/s
 reuse=e.load(base/'REUSED_MF_SCORE.json');req(reuse['status']=='reused_identical_input' and reuse['new_tracker_invocations']==0 and reuse['pair_id']==s,'reuse receipt differs')
 n=e.bound(reuse['native_metric_inputs']);a=e.bound(reuse['auto_metric_inputs']);ready=e.bound(reuse['release_evidence']);req(ready['status']=='case_ready' and ready['summary']['passed'] is True and ready['metric_inputs_sha256']==reuse['auto_metric_inputs']['sha256'],'case release failed')
 for key in ('source_original','source_prepared_video','source_score_video','source_preparation_record'):req(n[key]['sha256']==a[key]['sha256'],'reuse source changed')
 req(n['score_frame_indices']==a['score_frame_indices']==list(range(item['valid_frames'])) and n['input_to_original_frame']==a['input_to_original_frame'],'reuse physical time differs')
 e.media(item,'reference_video_path',n['source_prepared_video']['sha256']);e.media(item,'ordinary_video_path',n['edited']['native']['full_video']['sha256']);e.media(item,'guided_video_path',a['edited']['auto']['full_video']['sha256'])
 for name,left,right in [('full_video_identity_proof',n['edited']['native']['full_video'],a['edited']['auto']['full_video']),('score_input_identity_proof',n['edited']['native']['score_video'],a['edited']['auto']['score_video'])]:
  proof=e.bound(reuse[name]);req(reuse[name]['exact'] and proof['same_physical_timebase'] and proof['comparison']['exact'] and proof['cuda_initialized'] is False,'RGB/PTS proof failed');req(proof['left']==left and proof['right']==right,'RGB/PTS compared other media')
 score=e.bound(reuse['cached_native_score']);value=validate_reports(e,score,n,item,'native');req(value==reuse['motion_fidelity'],'reused score value differs')
 req(score['source_report']==reuse['source_report'] and score['target_report']==reuse['target_report'] and score['official_vendor']==reuse['official_vendor'],'reuse track/runtime differs')
 return value,value,e.paths,'全点官方MF；自动版实际0次干预，已证明完整视频及评分输入RGB/PTS逐位相同，按正式收据复用普通编辑分数。'
def process(item):
 out={'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','source_files':[],'source_sha256':{},'valid_frames':item['valid_frames'],'scope':'尚无完成且与本条媒体精确绑定的正式MF；不代表0分。','protocol':PROTOCOL}
 k=int(item['id'].split('_')[0][1:])
 if k not in NAMES and k!=55:return out,None
 try:
  n,g,files,scope=reused(item) if k==55 else normal(item,k)
  out.update(native=n,guided=g,delta=g-n,status='complete',source_files=list(files),source_sha256=files,scope=scope)
  return out,None
 except (ValueError,KeyError,OSError) as exc:return out,str(exc)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args();p=ROOT/'inventory/ivebench.json';d=read(p);before=copy.deepcopy(d);issues={};counts={};examples={}
 for item in d['items']:
  metric,error=process(item);item['quantitative_metrics']={'motion_fidelity':metric}
  if item['id']=='r89_short_0358':
   source=DEV/'h3-ive-subject-capacity-metrics-r89-20261018/audit/visual_review_short0358/REVIEW.json';v=read(source);req(v['valid_frames']==105 and v['fps']==24 and len(v['events'])==3,'event annotation scope differs')
   gate=Path(next(x for x in item['evidence_paths'] if x.endswith('PAIR_RUNTIME_GATE.json')));req(v['actual_gate']['sha256']==sha(gate),'event gate differs')
   item['quantitative_metrics']['event_timing']={'measurement':'逐帧视觉标注','fps':24,'events':[{'name':e['event'],'source_frames':e['source_frame_boundary'],'native_frames':e['native_frame_boundary'],'guided_frames':e['forced_frame_boundary']} for e in v['events']],'source_file':str(source),'source_sha256':sha(source),'scope':'事件发生于标注区间内；画面模糊导致边界存在不确定性。','annotator':v['reviewer']}
  counts[metric['status']]=counts.get(metric['status'],0)+1
  if error:issues[item['id']]=error
  if metric['status']=='complete':examples[item['id']]={k:metric[k] for k in ['native','guided','delta','valid_frames']}
 report={'counts':counts,'issues':issues,'complete':examples,'inventory_before_sha256':sha(p),'scope':'Existing JSON import only, no score/GPU/model execution'}
 (AUDIT/'DRY_RUN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if args.apply:
  req(not (AUDIT/'PREVIOUS_IVEBENCH.json').exists(),'already applied; explicit next version required');(AUDIT/'PREVIOUS_IVEBENCH.json').write_bytes(p.read_bytes())
  for old,new in zip(before['items'],d['items']):req({k:v for k,v in new.items() if k!='quantitative_metrics'}==old,'nonmetric field changed')
  tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p);report['inventory_after_sha256']=sha(p);(AUDIT/'IMPORT_RECEIPT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
