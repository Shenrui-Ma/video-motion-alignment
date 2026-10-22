"""Exact actual-noise binding; historical cross-host signatures are diagnostics."""
from pathlib import Path
from . import transport as t
from .dependencies import readout

def clean_record(v):
 if isinstance(v,dict):return {k:clean_record(x) for k,x in v.items() if k!='tensor_file'}
 if isinstance(v,list):return [clean_record(x) for x in v]
 return v

def sig(v):return {k:x for k,x in readout.tensor_signature(v).items() if k in ('shape','dtype','sha256')}

class HistoricalPairGate:
 def __init__(self):self.first_on=None;self.done=set();self.records={};self.case=None
 def native_comparable(self,n):return self.first_on is None or n<=self.first_on
 def begin(self,s,noise):
  t.bindings();self.case=t.case_for(s.config.run_id);old=t.read_json(t.ROOT/self.case['parent_conditioning']);cap=t.read_json(t.ROOT/self.case['parent_captures']);n=t.read_json(t.ROOT/self.case['parent_noise']);spec=t.read_json(t.ROOT/'configs/ACTUAL_NOISE.json')
  t.require(s.seed==self.case['seed']==cap['seed']==n['signature']['seed'],'seed mismatch');t.require(s.grid.tolist()==cap['sigmas_video'],'full sigma grid mismatch')
  t.require(readout.tensor_signature(noise)==cap['noise'],'packed actual noise mismatch');t.require([sig(x) for x in s.raw(noise)]==spec['actual_noise_streams'],'actual AV noise differs')
  current=t.read_json(t.ROOT/'audit'/f'{s.config.run_id}_conditioning.json');t.require(current['prompt']==old['prompt']==self.case['prompt'],'historical prompt differs')
  t.require(len(current['native_vae_calls'])==1 and current['target_latent_shapes']==old['target_latent_shapes'],'current reference count/shape differs')
  self.records={x['step_zero_based']:x for x in cap['captures']}
  fields=['input_video','native_vae_calls','conditioning_embedding','token_tags','packed_layout']
  s.audit['counterfactual']['pair_gates'].append({'gate':'initial_binding','pass':True,'seed':s.seed,'actual_initial_AV_noise_exact':True,'same_run_condition_signature':s.initial_condition['sha256'],'historical_condition_signatures':{k:{'current':clean_record(current[k]),'historical':clean_record(old[k]),'equal':clean_record(current[k])==clean_record(old[k])} for k in fields},'cross_host_equality_required':False})
 def branch(self,s,x,output,row):
  n,b=row['physical_index'],row['branch'];g={'gate':'native_prefix','physical_index':n,'branch':b,'first_on':self.first_on}
  if b!='native' or not self.native_comparable(n):g.update(status='not_applicable',reason='guided or changed closed-loop state')
  else:
   old=self.records[n];t.require(row['sigma']==old['sigma_video'] and row['sigma_next']==old['sigma_next_video'],'historical sigma differs')
   g.update(status='cross_host_diagnostic',current=row['normalized_stream_signatures'],historical=[old['video'],old['audio']],signature_equal=row['normalized_stream_signatures']==[old['video'],old['audio']]);self.done.add(n)
  s.audit['counterfactual']['pair_gates'].append(g)
 def decision(self,s,n,decision):
  if decision['chosen_full'] and self.first_on is None:
   self.first_on=n;s.audit['counterfactual']['first_actual_full']=n;s.audit['counterfactual']['old_native_future_eligibility']='N/A after first actual ON'
 def finish(self,s):
  t.require({n for n in self.records if self.native_comparable(n)}<=self.done,'missing prefix diagnostic')
  s.audit['counterfactual']['native_preservation']={'zero_Full':self.first_on is None,'first_on':self.first_on,'status':'same-run invariants verified; historical equality recorded only','cross_host_equality_required':False}
