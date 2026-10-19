"""R32 actual current Native0..2 and actual processed condition tree, before firstFull2."""
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

FIELDS=('physical_index','branch','nfe_index','seed','sigma','sigma_next','condition_sha256','reference_sha256','raw_stream_signatures')
def actual_prefix(row,expected,current_path):
    n=expected['index'];old_path=Path(expected['path']);old=expected['branch_record']
    t.require(t.sha(old_path)==expected['file_sha256']==old['file_sha256'],'historical Native branch PT SHA differs')
    saved=torch.load(old_path,map_location='cpu',weights_only=True);current=torch.load(current_path,map_location='cpu',weights_only=True)
    t.require(set(saved)==set(current)=={'video','audio','metadata'},'prefix PT schema')
    t.require(saved['metadata']=={k:old[k] for k in FIELDS} and current['metadata']=={k:row[k] for k in FIELDS},'actual prefix metadata differs')
    t.require(row['physical_index']==old['physical_index']==n and row['branch']==old['branch']=='native' and row['nfe_index']==old['nfe_index']==n and row['seed']==old['seed']==2026101701,'prefix identity')
    t.require(row['sigma']==old['sigma'] and row['sigma_next']==old['sigma_next'] and row['reference_sha256']==old['reference_sha256'],'prefix grid/reference')
    t.require(row['same_input']==old['same_input'],'actual prestate packed signature differs')
    for value in (saved,current):
        for key,shape in (('video',(1,24,42,46,82)),('audio',(1,32,2,235))):
            v=value[key];t.require(v.dtype==torch.float32 and tuple(v.shape)==shape and bool(torch.isfinite(v).all()),'prefix AV schema')
    for value,record in ((saved,old),(current,row)):
        t.require([readout.tensor_signature(value[k]) for k in ('video','audio')]==record['normalized_stream_signatures'],'normalized prefix signature differs')
        t.require([readout.tensor_signature(value['video']),readout.tensor_signature(value['audio']*4)]==record['raw_stream_signatures'],'raw prefix/audio scale differs')
    t.require(all(torch.equal(saved[k],current[k]) for k in ('video','audio')),'actual Native prefix differs')
    return {'physical_index':n,'branch':'native','status':'pass','actual_tensor_equal':True,'old_file':str(old_path),'old_file_sha256':expected['file_sha256'],'chosen_comparable':n<2,'same_input_signature_equal':True,'historical_packed_input_tensor_comparison':'R32 input2 rawPT not archived; recorded per-forward packed signature only','historical_processed_tree_comparison':'actual canonical tree exact modulo two corresponding UUID fields'}

class HistoricalPairGate:
    def __init__(self):self.first_on=None;self.done=set();self.selected=[]
    def begin(self,s,noise):
        b=t.bindings();case=t.case_for(s.config.run_id)
        old=t.read_json(t.ROOT/'configs/parent_conditioning.json');noises=t.read_json(t.ROOT/'configs/parent_noise.json');captures=t.read_json(t.ROOT/'configs/parent_captures.json');protocol=t.read_json(t.ROOT/'PROTOCOL.json');cf=t.read_json(t.ROOT/'configs/parent_counterfactual.json')['counterfactual']
        t.require(s.seed==case['seed']==captures['seed']==noises['signature']['seed']==2026101701,'seed mismatch')
        t.require(s.grid.tolist()==captures['sigmas_video']==protocol['schedule']['video_grid']==cf['full_grid'],'full grid mismatch')
        t.require([signature_without_bytes(readout.tensor_signature(v)) for v in s.raw(noise)]==noises['actual_noise_streams'],'actual AV noise mismatch')
        condition_audit_matches(t.read_json(t.ROOT/'audit'/f'{s.config.run_id}_conditioning.json'),old)
        t.require(signature_without_bytes(s.reference_signature)==clean_record(old['native_vae_calls'][1]['latent']),'clean ref mismatch')
        t.require(canonical_condition(s.initial_condition['tree'])==canonical_condition(cf['conditioning']['tree']),'actual R32 processed/original condition tree differs beyond twoUUIDs')
        self.records=protocol['actual_native_prefix_evidence'];t.require([r['index'] for r in self.records]==[0,1,2],'three prefix records required')
        payload=s.initial_condition['tree']['processed']['positive'][0]['model_conds']['minimax_payload']['cond']
        t.require(payload['seed']==s.seed and payload.get('visual_cond_noise_aug',.999)==.999 and payload.get('audio_cond_noise_aug',1.0)==1.0,'augmentation differs')
        core=t.read_json(t.ROOT/'configs/parent_core_hashes.json')
        for name in ('comfy/ldm/minimax/model.py','comfy/model_base.py'):t.require(t.sha(Path(b['comfy'])/name)==core[name],'actual augmentation code differs')
        s.audit['counterfactual']['pair_gates'].append({'gate':'initial_binding','pass':True,'seed':s.seed,'actual_clean_conditions_and_AV_noise_exact':True,'historical_processed_condition_tree':'R32 actual exact canonical comparison; two positive UUID fields only','historical_packed_input':'Native0..2 recorded same_input signature, raw2tensor unavailable','current_condition_sha256':s.initial_condition['sha256'],'current_initial_packed_noise':readout.tensor_signature(noise)})
    def branch(self,s,x,output,row):
        n,b=row['physical_index'],row['branch']
        if b=='native' and n<=2:
            result=actual_prefix(row,self.records[n],row['file']);self.done.add(n)
        else:result={'physical_index':n,'branch':b,'status':'not_applicable','reason':'Full2 and all future states diverge permanently from R32 local trajectory'}
        s.audit['counterfactual']['pair_gates'].append(dict(gate='native_prefix',**result))
    def decision(self,s,n,decision):
        if decision['chosen_full']:
            t.require(n in (2,4,5,6) and n not in self.selected and self.done=={0,1,2},'fixed Full requires all common prefix gates')
            self.selected.append(n)
            if self.first_on is None:self.first_on=n;s.audit['counterfactual']['first_actual_full']=n
    def finish(self,s):
        t.require(self.done=={0,1,2} and self.first_on==2 and self.selected==[2,4,5,6],'missing fixed/prefix gates')
        s.audit['counterfactual']['native_preservation']={'first_on':2,'status':'divergent_after_Full2','eligible_current_native_indices':[0,1,2],'eligible_chosen_indices':[0,1],'future_replay':'permanently_not_applicable'}
