"""Compare new same-host conditions. Historical Native metadata is descriptive."""
import copy,json
from pathlib import Path
from r115_contract import ROOT,RUNS,read,sha,require

def comparable_conditions(a,b):
 a=copy.deepcopy(a);a['run_id']=b['run_id'];return a==b

def validate_parent_condition(current,source,root=ROOT):
 root=Path(root);run=current['run_id'];require(source=='long_0174' and run in RUNS,'unknown condition run')
 if run==RUNS[0]:
  return {'passed':True,'source_id':source,'current_run':run,'stage':'before_DiT','scope':'first new arm: shared condition tensors verified by H3PairAudit; historical cross-host equality not required','comparison':'self_integrity'}
 prior=root/'audit'/(RUNS[0]+'_conditioning.json');previous=read(prior)
 require(comparable_conditions(current,previous),'new arms have different conditions before DiT')
 return {'passed':True,'source_id':source,'current_run':run,'stage':'before_DiT','comparison':'two_new_arms_exact','paired_run':RUNS[0],'paired_condition_sha256':sha(prior)}
