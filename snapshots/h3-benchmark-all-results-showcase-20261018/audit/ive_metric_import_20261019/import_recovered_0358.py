"""Bind the already completed 0358 official MF to the existing inventory row."""
import argparse,copy,math
from pathlib import Path
from import_scores import *
RECOVERY=DEV/'h3-quantitative-evaluation-recovery-20261019'
MAP['/data4/researcher/h3_runs/quantitative_evaluation_recovery_20261019']=RECOVERY
OUT=AUDIT/'recovered_0358'
def verify(item):
 e=Evidence();m=e.load(RECOVERY/'INPUTS.json');g=e.load(RECOVERY/'inputs/PAIR_RUNTIME_GATE.json',m['gate_sha256'])
 req(item['id']=='r89_short_0358' and item['valid_frames']==m['valid_frames']==105,'row/support mismatch')
 req(m['source_id']==g['source_id']=='short_0358' and g['passed'] is True and all(x is True for x in g['checks'].values()),'actual gate failed')
 req(m['total_frames']==107 and m['fps']==item['fps']==24 and m['crop_xywh']==[16,8,1280,720],'physical support mismatch')
 actual_gate=next(Path(p) for p in item['evidence_paths'] if p.endswith('PAIR_RUNTIME_GATE.json'))
 req(sha(actual_gate)==m['gate_sha256'],'inventory gate differs');e.load(actual_gate,m['gate_sha256'])
 prov=e.load(RECOVERY/'inputs/source_provenance.json',m['source_provenance_sha256'])
 reports={}
 for role,field in [('source','reference_video_path'),('native','ordinary_video_path'),('forced','guided_video_path')]:
  r=m['roles'][role];e.media(item,field,r['full_sha256'])
  for prefix in ['full','score']:req(sha(RECOVERY/r[prefix+'_file'])==r[prefix+'_sha256'],role+' input bytes differ')
  if role!='source':req(g['runs'][role]['video']['sha256']==r['full_sha256'] and g['runs'][role]['valid_frames']==105,'gate output differs')
  q=e.load(RECOVERY/'tracks'/role/'REPORT.json');reports[role]=q
  req(q['passed'] is True and q['pair_id']=='short_0358' and q['method']==role,'tracker role/pass mismatch')
  req(q['official_commit']==OFFICIAL and q['vendor']['commit']==OFFICIAL and q['checkpoint_sha256']==CHECKPOINT and q['tracker']==TRACKER,'tracker protocol differs')
  req(q['selection_sha256']==sha(RECOVERY/'INPUTS.json') and e.bound(q['input_manifest'])==m,'tracking input manifest differs')
  req(q['score_video']['sha256']==r['score_sha256'] and q['source_prepared_sha256']==m['roles']['source']['full_sha256'] and q['source_score_sha256']==m['roles']['source']['score_sha256'],'tracking source differs')
  req(q['effective_frame_count']==105 and q['score_frame_indices']==list(range(105)) and q['decoded_frame_md5']==r['score_frame_md5'] and len(r['score_frame_md5'])==105,'tracker support/pixels differ')
  req(sha(RECOVERY/'tracks'/role/'tracks.npz')==q['tracks_sha256'],'actual tracks differ')
  req(q['tracks_shape']==[1,105,100,2],'tracks geometry differs')
  for k in ['torch_version','cuda_version','official_commit','tracker','checkpoint_sha256','effective_frame_count','score_frame_indices','gpu_uuid']:
   req(q[k]==reports['source'][k], 'same-host tracker mismatch '+k)
 values={}
 for role in ['native','forced']:
  s=e.load(RECOVERY/'results'/f'{role}.json')
  req(s['schema']=='h3-ivebench-official-mf-cached-result-v1' and s['pair_id']=='short_0358' and s['method']==role,'score role mismatch')
  req(s['official_vendor']==reports[role]['vendor']==reports['source']['vendor'] and s['checkpoint_sha256']==CHECKPOINT,'score protocol differs')
  req(s['device']=='cpu' and s['cuda_initialized'] is False,'unexpected score execution')
  for tag,track_role in [('source','source'),('target',role)]:
   req(e.bound(s[tag+'_report'])==reports[track_role] and s[tag+'_tracks_sha256']==reports[track_role]['tracks_sha256'],'score track/report mismatch')
  req(math.isfinite(s['motion_fidelity']),'invalid score');values[role]=s['motion_fidelity']
 summary=e.load(RECOVERY/'results/SUMMARY.json')
 req(summary['input_sha256']==sha(RECOVERY/'INPUTS.json') and summary['same_host_fresh_tracks'] is True,'summary input mismatch')
 req(summary['ordinary']==values['native'] and summary['guided']==values['forced'] and summary['guided_minus_ordinary']==values['forced']-values['native'],'summary values differ')
 metric={'native':values['native'],'guided':values['forced'],'delta':values['forced']-values['native'],'higher_is_better':True,'status':'complete','source_files':list(e.paths),'source_sha256':e.paths,'valid_frames':105,'scope':'全105有效帧的全点官方MF；三份轨迹在同一主机重新提取。该分数衡量运动相似性，时延另见逐帧事件区间。','protocol':PROTOCOL}
 return metric
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');a=ap.parse_args();p=ROOT/'inventory/ivebench.json';d=read(p);old=copy.deepcopy(d);row=next(x for x in d['items'] if x['id']=='r89_short_0358');metric=verify(row);OUT.mkdir(exist_ok=True)
 if a.apply:
  req(not (OUT/'PREVIOUS_IVEBENCH.json').exists(),'already applied');(OUT/'PREVIOUS_IVEBENCH.json').write_bytes(p.read_bytes());row['quantitative_metrics']['motion_fidelity']=metric
  for before,after in zip(old['items'],d['items']):
   if before['id']!='r89_short_0358':req(before==after,'other row changed')
   else:
    b=copy.deepcopy(before);b['quantitative_metrics']['motion_fidelity']=metric;req(b==after,'non-MF field changed')
  tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
 report={'metric':metric,'inventory_sha256':sha(p),'applied':a.apply,'other_fields_unchanged':True};(OUT/('APPLIED.json' if a.apply else 'DRY_RUN.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'values':{k:metric[k] for k in ['native','guided','delta']},'inventory_sha256':sha(p),'applied':a.apply}))
