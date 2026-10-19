"""Actual R26 normalized AV prefix; historical processed tree/raw input absent."""
import copy,uuid
from pathlib import Path
import torch
from . import transport as t
from .dependencies import readout

def signature_without_bytes(v):return {k:v[k] for k in ('shape','dtype','sha256')}
def clean_record(value):
    if isinstance(value,dict):return {k:clean_record(v) for k,v in value.items() if k!='tensor_file'}
    if isinstance(value,list):return [clean_record(v) for v in value]
    return value

def canonical_condition(tree):
    value=copy.deepcopy(tree)
    a=value['original']['positive'][0]['uuid'];b=value['processed']['positive'][0]['uuid']
    if a!=b or str(uuid.UUID(a))!=a:raise ValueError('condition UUID correspondence differs')
    value['original']['positive'][0]['uuid']='<allowed-run-UUID>'
    value['processed']['positive'][0]['uuid']='<allowed-run-UUID>'
    return value

def condition_audit_matches(actual,old):
    keys=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
    t.require(len(actual['native_vae_calls'])==len(old['native_vae_calls'])==2,'reference inventory differs')
    for key in keys:t.require(clean_record(actual[key])==clean_record(old[key]),'producer evidence differs: '+key)

def actual_prefix(row,expected,current_path):
    n=expected['index'];old_path=Path(expected['path']);old_meta=expected['metadata']
    t.require(t.sha(old_path)==expected['file_sha256'],'historical native PT SHA differs')
    saved=torch.load(old_path,map_location='cpu',weights_only=True);current=torch.load(current_path,map_location='cpu',weights_only=True)
    t.require(set(saved)==set(current)=={'video','audio','metadata'},'prefix PT schema')
    t.require(all(current['metadata'][k]==row[k] for k in ('physical_index','branch','nfe_index','seed','sigma','sigma_next')),'current prefix metadata binding')
    m=saved['metadata']
    t.require(m=={k:v for k,v in old_meta.items() if k not in ('file','capture_seconds')},'historical PT metadata differs from frozen record')
    t.require(m['schema']=='h3-x0-readout-v1' and m['snapshot_kind']=='x0_estimate' and m['step_zero_based']==n and m['model_call_one_based']==n+1 and m['total_steps']==20 and m['seed']==2026101701,'historical native metadata')
    t.require(row['physical_index']==n and row['branch']=='native' and row['nfe_index']==n and row['seed']==2026101701,'current native metadata')
    t.require(m['geometry']=={'width':1312,'height':736,'frames':141,'fps':24} and m['normalization_stage']=='after_process_latent_out' and m['video_latent_scale_factor']==1.0 and m['audio_scale']==4.0,'historical normalization/geometry differs')
    t.require(m['sigma_video']==row['sigma'] and m['sigma_next_video']==row['sigma_next'] and m['sigma_audio']==row['sigma']/(4-3*row['sigma']),'paired sigma mismatch')
    t.require([readout.tensor_signature(saved[k]) for k in ('video','audio')]==[m[k] for k in ('video','audio')]==row['normalized_stream_signatures'],'paired normalized signature differs')
    for key,shape in (('video',(1,24,42,46,82)),('audio',(1,32,2,235))):
        t.require(saved[key].dtype==torch.float32 and tuple(saved[key].shape)==shape and bool(torch.isfinite(saved[key]).all()),'historical AV shape/dtype/finite')
    t.require(all(torch.equal(saved[k],current[k]) for k in ('video','audio')),'actual prefix tensor differs')
    return {'physical_index':n,'branch':'native','status':'pass','actual_tensor_equal':True,'old_file':str(old_path),'old_file_sha256':expected['file_sha256'],'chosen_comparable':n<4,'historical_packed_input_comparison':'not_available','historical_processed_tree_comparison':'not_available'}

class HistoricalPairGate:
    def __init__(self):self.first_on=None;self.done=set()
    def begin(self,s,noise):
        b=t.bindings();case=t.case_for(s.config.run_id)
        old=t.read_json(t.ROOT/'configs/parent_conditioning.json');noises=t.read_json(t.ROOT/'configs/parent_noise.json');captures=t.read_json(t.ROOT/'configs/parent_captures.json');protocol=t.read_json(t.ROOT/'PROTOCOL.json')
        t.require(s.seed==case['seed']==captures['seed']==noises['signature']['seed']==2026101701,'seed mismatch')
        t.require(s.grid.tolist()==captures['sigmas_video']==protocol['schedule']['video_grid'],'full grid mismatch')
        t.require([signature_without_bytes(readout.tensor_signature(v)) for v in s.raw(noise)]==noises['actual_noise_streams'],'actual AV noise mismatch')
        condition_audit_matches(t.read_json(t.ROOT/'audit'/f'{s.config.run_id}_conditioning.json'),old)
        t.require(signature_without_bytes(s.reference_signature)==clean_record(old['native_vae_calls'][1]['latent']),'clean ref mismatch')
        canonical_condition(s.initial_condition['tree'])
        self.records=protocol['actual_native_prefix_evidence']
        t.require([r['index'] for r in self.records]==list(range(5)),'fixed five prefix records required')
        payload=s.initial_condition['tree']['processed']['positive'][0]['model_conds']['minimax_payload']['cond']
        t.require(payload['seed']==s.seed and payload.get('visual_cond_noise_aug',.999)==.999 and payload.get('audio_cond_noise_aug',1.0)==1.0,'augmentation differs')
        core=t.read_json(t.ROOT/'configs/parent_core_hashes.json')
        for name in ('comfy/ldm/minimax/model.py','comfy/model_base.py'):t.require(t.sha(Path(b['comfy'])/name)==core[name],'actual augmentation code differs')
        s.audit['counterfactual']['pair_gates'].append({'gate':'initial_binding','pass':True,'seed':s.seed,'actual_clean_conditions_and_AV_noise_exact':True,'historical_processed_condition_tree':'not_archived','historical_packed_input':'not_archived','current_condition_sha256':s.initial_condition['sha256'],'current_initial_packed_noise':readout.tensor_signature(noise)})
    def branch(self,s,x,output,row):
        n,b=row['physical_index'],row['branch']
        if b=='native' and n<=4:
            result=actual_prefix(row,self.records[n],row['file']);self.done.add(n)
        else:result={'physical_index':n,'branch':b,'status':'not_applicable','reason':'Full4 and all future states diverge permanently from R26 Native'}
        s.audit['counterfactual']['pair_gates'].append(dict(gate='native_prefix',**result))
    def decision(self,s,n,decision):
        if decision['chosen_full']:
            t.require(n==4 and self.first_on is None and self.done==set(range(5)),'only fixed Full4 after all current Native bridges')
            self.first_on=4;s.audit['counterfactual']['first_actual_full']=4
    def finish(self,s):
        t.require(self.done==set(range(5)) and self.first_on==4,'missing eligible exact Native prefix')
        s.audit['counterfactual']['native_preservation']={'first_on':4,'status':'divergent_after_Full4','eligible_current_native_indices':list(range(5)),'eligible_chosen_indices':list(range(4)),'future_replay':'permanently_not_applicable'}
