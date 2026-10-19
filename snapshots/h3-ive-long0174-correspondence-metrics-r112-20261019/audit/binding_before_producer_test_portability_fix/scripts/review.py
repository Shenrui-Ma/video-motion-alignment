"""Inherited physical events and complete valid-frame review for the two R112 outputs."""
import copy
from common import ROOT,read,save,bound,require
ARMS=('fixed_one_bin','matched_one_bin')

def delay_interval(source,edited):
 require(len(source)==len(edited)==2 and all(type(i) is int for i in [*source,*edited]),'integer physical-frame intervals required')
 require(0<=source[0]<=source[1]<145 and 0<=edited[0]<=edited[1]<145,'event interval outside valid support')
 f=[edited[0]-source[1],edited[1]-source[0]]
 return {'frames':f,'seconds':[i/24 for i in f],'interpretation':'visible annotation uncertainty; not a statistical confidence interval'}

def template(incoming,showcase):
 p=ROOT/'audit/full145_review/REVIEW_TEMPLATE.json'
 if p.exists():return p
 d=copy.deepcopy(read(ROOT/'configs/PREREGISTERED_EVENTS.json'));d.update(schema='r112-full145-review-template-v1',all_valid_frames_inspected=False,examined_frames_by_arm={a:[] for a in ARMS},basic_edit_task={a:'PENDING' for a in ARMS},motion_preservation={a:'PENDING' for a in ARMS},quality={a:'PENDING' for a in ARMS},evidence={'gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'collection':bound(incoming/'COLLECTION.json'),'frame_ledger':bound(showcase/'FRAME_LEDGER.json'),'inherited_events':bound(ROOT/'configs/PREREGISTERED_EVENTS.json')});save(p,d);return p

def validate_completed(value):
 expected=read(ROOT/'configs/PREREGISTERED_EVENTS.json');require(value['all_valid_frames_inspected'] is True,'full review pending');require(set(value['examined_frames_by_arm'])==set(ARMS),'wrong reviewed arms')
 for a in ARMS:require(value['examined_frames_by_arm'][a]==list(range(145)),'all145 valid frames required for '+a)
 require(len(value['events'])==len(expected['events'])==3,'registered event count changed')
 for row,old in zip(value['events'],expected['events']):
  for k in ['id','definition','source_frames','native_frames','fixed_frames','fixed_comparability']:require(row[k]==old[k],'registered event changed: '+k)
  for a in ARMS:
   if row[a+'_status']=='OBSERVED':require(row.get(a+'_delay')==delay_interval(row['source_frames'],row[a+'_frames']),'physical interval calculation differs')
   else:require(row[a+'_status'] in ['UNKNOWN','NOT_COMPARABLE','RIGHT_CENSORED','ALTERED'] and row[a+'_frames'] is None and row.get(a+'_delay') is None,'unobserved event has numeric delay')
 for k in ['source_frames','definition','native_status','fixed_status']:require(value['terminal_motion'][k]==expected['terminal_motion'][k],'terminal definition changed')
 for a in ARMS:
  require(value['terminal_motion'][a+'_status'] in ['OBSERVED','UNKNOWN','NOT_COMPARABLE','RIGHT_CENSORED','ALTERED'],'terminal review incomplete')
  for k in ['basic_edit_task','motion_preservation','quality']:require(value[k][a]!='PENDING','acceptance review incomplete')
 return True
