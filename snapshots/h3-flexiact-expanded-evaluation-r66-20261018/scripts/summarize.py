"""Keep all eight pairs and separate the two prespecified task groups."""
import argparse,math
from common import *
def summarize():
 verify_runtime();rows=[]
 for pair in PAIR_KEYS:
  info=pair_info(pair);row={**info,'edit_success':'PENDING_HUMAN_REVIEW','scores':{}}
  for method in METHODS:
   path=ROOT/'scores'/method/pair/'SCORE.json'
   if not path.exists():row['scores'][method]={'status':'PENDING','score':None};continue
   value=read(path);require(all(value[k]==info[k] for k in ['pair_key','motion_source_id','original_pair_id','group']) and value['method']==method,'score task binding differs')
   for key in ['reference_report','edit_report','reference_tracks','edited_tracks','producer_runtime_receipt','metric_inputs']:
    require(sha(value[key]['file'])==value[key]['sha256'],'score evidence changed: '+key)
   require(value['metric_adapter_sha256']==sha(METRIC/'metric_adapter.py'),'score numeric adapter differs')
   require(value['score'] is None or (isinstance(value['score'],(float,int)) and math.isfinite(value['score'])),'score must preserve undefined as null')
   row['scores'][method]={'status':value['status'],'score':value['score'],'evidence':bound(path)}
  a,b=[row['scores'][m]['score'] for m in METHODS];row['forced_minus_native']=b-a if a is not None and b is not None else None;rows.append(row)
 groups=[]
 for group,denominator in [('official_csv_identity_generalization',2),('official_assets_crosspair_extension',6)]:
  chosen=[x for x in rows if x['group']==group];require(len(chosen)==denominator,'fixed group denominator differs')
  complete=[x for x in chosen if x['forced_minus_native'] is not None]
  groups.append({'group':group,'prespecified_pair_denominator':denominator,'motion_source_denominator':len({x['motion_source_id'] for x in chosen}),'paired_finite_scores':len(complete),'pending_or_undefined_pairs':denominator-len(complete),'native_mean_on_paired_finite':sum(x['scores']['native']['score'] for x in complete)/len(complete) if complete else None,'forced_mean_on_paired_finite':sum(x['scores']['forced']['score'] for x in complete)/len(complete) if complete else None,'mean_paired_delta':sum(x['forced_minus_native'] for x in complete)/len(complete) if complete else None})
 return {'schema':'r66-mf-fixed-denominator-summary-v1','total_pairs':8,'distinct_motion_sources':5,'new_motion_sources':3,'groups':groups,'pairs':rows,'interpretation':'MF measures author-code trajectory similarity; appearance attainment, action type and physical lag need separate human/pose assessment. No aggregate mixes the six custom pairs with the two official CSV pairs.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 with cpu_lock():save(a.output,summarize());print(a.output)
