"""R14 normal native pairing; old post-augmentation tensors were not archived."""
from pathlib import Path
import torch
from . import transport as t
from .dependencies import readout

OLD_ROOT=Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016')
OLD_RUN='r14_s05_seed1313_native_host9'
CASE_SEED=2026101313

def signature_without_bytes(value):
 return {key:value[key] for key in ('shape','dtype','sha256')}

def clean_record(value):
 if isinstance(value,dict):return {k:clean_record(v) for k,v in value.items() if k!='tensor_file'}
 if isinstance(value,list):return [clean_record(v) for v in value]
 return value

def condition_audit_matches(actual,old):
 # Archived producer inputs/clean references are not processed H3 conditions.
 keys=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
       'conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
 for key in keys:t.require(clean_record(actual[key])==clean_record(old[key]),'G1 producer evidence differs: '+key)

def augmentation_contract(tree):
 positive=tree['processed']['positive'];t.require(len(positive)==1,'G1 unique processed positive')
 payload=positive[0]['model_conds']['minimax_payload']['cond']
 t.require(type(payload['seed']) is int and payload['seed']==CASE_SEED,'G1 augmentation seed differs')
 t.require(payload.get('visual_cond_noise_aug',0.999)==0.999 and payload.get('audio_cond_noise_aug',1.0)==1.0,'G1 augmentation amounts differ')
 return {'seed':payload['seed'],'visual_cond_noise_aug':0.999,'audio_cond_noise_aug':1.0,
         'historical_post_augmentation_tensor_available':False,
         'scope':'current processed payload seed + frozen helper code; no historical full-condition equality certificate'}

class HistoricalPairGate:
 def __init__(self):self.first_on=None;self.done=set();self.records={}
 def native_comparable(self,n):return self.first_on is None or n<=self.first_on
 def begin(self,s,noise):
  b=t.bindings();old=t.read_json(t.ROOT/'configs/parent_r14_conditioning.json')
  captures=t.read_json(t.ROOT/'configs/parent_r14_captures.json');noises=t.read_json(t.ROOT/'configs/parent_r14_noise.json')
  t.require(s.seed==CASE_SEED==captures['seed']==noises['signature']['seed'],'G1 seed differs')
  t.require(s.grid.tolist()==captures['sigmas_video'],'G1 full grid differs')
  t.require(readout.tensor_signature(noise)==captures['noise'],'G1 packed sampler noise differs')
  streams=s.raw(noise)
  t.require([signature_without_bytes(readout.tensor_signature(v)) for v in streams]==noises['actual_noise_streams'],'G1 raw noise streams differ')
  current=t.read_json(t.ROOT/'audit'/f'{s.config.run_id}_conditioning.json')
  condition_audit_matches(current,old)
  t.require(signature_without_bytes(s.reference_signature)==clean_record(old['native_vae_calls'][1]['latent']),'G1 clean video reference differs')
  aug=augmentation_contract(s.initial_condition['tree'])
  core_hashes=t.read_json(t.ROOT/'configs/parent_core_hashes.json')
  for name in ('comfy/ldm/minimax/model.py','comfy/model_base.py'):
   t.require(t.sha(Path(b['comfy'])/name)==core_hashes[name],'G1 augmentation/condition source differs')
  self.records={row['step_zero_based']:row for row in captures['captures']}
  s.audit['counterfactual']['pair_gates'].append({'gate':'G1_initial','pass':True,'augmentation':aug,
   'raw_noise_streams_exact':True,'producer_inputs_and_clean_refs_exact':True,
   'historical_processed_condition_equality':'unavailable; not claimed','current_full_condition_sha256':s.initial_condition['sha256']})
 def branch(self,s,x,output,row):
  n,b=row['physical_index'],row['branch']
  if b!='native' or not self.native_comparable(n):
   s.audit['counterfactual']['pair_gates'].append({'gate':'G1_native_checkpoint','physical_index':n,'branch':b,
     'status':'not_applicable','reason':'Full branch or state after first actual Full','first_on':self.first_on})
   return
  if n not in self.records:return
  old=self.records[n]
  t.require(row['sigma']==old['sigma_video'] and row['sigma_next']==old['sigma_next_video'],'G1 paired sigma differs')
  t.require(row['normalized_stream_signatures']==[old['video'],old['audio']],'G1 available native AV checkpoint differs')
  path=OLD_ROOT/'audit/x0'/OLD_RUN/old['file'];saved=torch.load(path,map_location='cpu',weights_only=True)
  actual=torch.load(row['file'],map_location='cpu',weights_only=True)
  for key in ('video','audio'):
   t.require(readout.tensor_signature(saved[key])==old[key],'old R14 tensor changed')
   t.require(torch.equal(saved[key],actual[key]),'G1 actual native AV tensors differ')
  self.done.add(n)
  s.audit['counterfactual']['pair_gates'].append({'gate':'G1_native_checkpoint','physical_index':n,'branch':b,'pass':True,
    'tensor_equal':True,'old_file':str(path),'old_file_sha256':t.sha(path)})
 def decision(self,s,n,decision):
  if decision['chosen_full'] and self.first_on is None:
   t.require(n>=6,'Full chosen in prefix');self.first_on=n
   s.audit['counterfactual']['normal_preservation']={'zero_Full':False,'first_on':n,
    'status':'scientific_failure','current_native_comparable':True,
    'future_old_native_pairing':'permanently not applicable, even after later OFF'}
 def finish(self,s):
  required={n for n in self.records if self.native_comparable(n)}
  t.require(required<=self.done,'missing eligible historical checkpoints')
  bridge=[g for g in s.audit['counterfactual']['pair_gates'] if g['gate']=='G2_current_native010']
  t.require(len(bridge)==1,'missing/duplicate G2 record')
  if self.native_comparable(10):t.require(bridge[0].get('pass') is True,'eligible G2 did not pass')
  else:t.require(bridge[0].get('status')=='not_applicable','invalid divergent G2 status')
  if self.first_on is None:s.audit['counterfactual']['normal_preservation']={'zero_Full':True,'first_on':None,'status':'pending_final_replay'}
