"""Available actual Native prefixes, with permanent causal branch qualification."""
from pathlib import Path
import torch
from . import transport as t
from .dependencies import readout

def signature_without_bytes(value):return {k:value[k] for k in ('shape','dtype','sha256')}
def clean_record(value):
    if isinstance(value,dict):return {k:clean_record(v) for k,v in value.items() if k!='tensor_file'}
    if isinstance(value,list):return [clean_record(v) for v in value]
    return value

def condition_audit_matches(actual,old):
    keys=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
          'conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
    t.require(len(actual['native_vae_calls'])==len(old['native_vae_calls'])==2,'reference inventory differs')
    for key in keys:t.require(clean_record(actual[key])==clean_record(old[key]),'producer evidence differs: '+key)

def compare_embedding_tensors(current,saved,expected):
    t.require(isinstance(current,torch.Tensor) and isinstance(saved,torch.Tensor),'embedding tensor schema')
    t.require(signature_without_bytes(readout.tensor_signature(saved))==clean_record(expected),'archived embedding content differs')
    t.require(signature_without_bytes(readout.tensor_signature(current))==clean_record(expected),'actual embedding content differs')
    t.require(torch.equal(current.detach().to('cpu'),saved),'actual embedding tensor differs')

def check_parent_embedding(s,case,old):
    original=s.guider.original_conds['positive']
    t.require(len(original)==1 and 'cross_attn' in original[0],'official original conditioning schema differs')
    current=original[0]['cross_attn']
    t.require(isinstance(current,torch.Tensor),'actual original embedding missing')
    expected=clean_record(old['conditioning_embedding'])
    t.require(signature_without_bytes(readout.tensor_signature(current))==expected,'actual embedding content differs')
    if 'tensor_file' not in old['conditioning_embedding']:
        return {'actual_signature_equal':True,'signature':expected,'actual_tensor_equal':None,
                'historical_tensor_available':False,'scope':'actual original clean Qwen signature matches archived signature; old tensor entity and processed tree unavailable'}
    relative='audit/'+old['conditioning_embedding']['tensor_file']
    expected_file=t.read_json(t.ROOT/case['parent_file_inventory'])[relative]
    path=Path(case['parent_root'])/relative
    t.require(path.stat().st_size==expected_file['bytes'] and t.sha(path)==expected_file['sha256'],'archived embedding file differs')
    saved=torch.load(path,map_location='cpu',weights_only=True)
    compare_embedding_tensors(original[0]['cross_attn'],saved,old['conditioning_embedding'])
    return {'file':str(path),'file_sha256':expected_file['sha256'],'actual_tensor_equal':True,'scope':'clean Qwen embedding, not a historical post-augmentation tree'}

class HistoricalPairGate:
    def __init__(self):self.first_on=None;self.done=set();self.records={};self.case=None
    def native_comparable(self,n):return self.first_on is None or n<=self.first_on
    def begin(self,s,noise):
        b=t.bindings();self.case=t.case_for(s.config.run_id)
        old=t.read_json(t.ROOT/self.case['parent_conditioning'])
        captures=t.read_json(t.ROOT/self.case['parent_captures']);noises=t.read_json(t.ROOT/self.case['parent_noise'])
        t.require(s.seed==self.case['seed']==captures['seed']==noises['signature']['seed'],'seed mismatch')
        t.require(s.grid.tolist()==captures['sigmas_video'],'full grid mismatch')
        t.require(readout.tensor_signature(noise)==captures['noise'],'packed sampler noise mismatch')
        t.require([signature_without_bytes(readout.tensor_signature(v)) for v in s.raw(noise)]==noises['actual_noise_streams'],'noise streams mismatch')
        current=t.read_json(t.ROOT/'audit'/f'{s.config.run_id}_conditioning.json');condition_audit_matches(current,old)
        embedding_record=check_parent_embedding(s,self.case,old)
        t.require(signature_without_bytes(s.reference_signature)==clean_record(old['native_vae_calls'][1]['latent']),'clean reference mismatch')
        payload=s.initial_condition['tree']['processed']['positive'][0]['model_conds']['minimax_payload']['cond']
        t.require(payload['seed']==s.seed and payload.get('visual_cond_noise_aug',.999)==.999 and payload.get('audio_cond_noise_aug',1.0)==1.0,'augmentation contract differs')
        core=t.read_json(t.ROOT/'configs/parent_core_hashes.json')
        for name in ('comfy/ldm/minimax/model.py','comfy/model_base.py'):
            t.require(t.sha(Path(b['comfy'])/name)==core[name],'actual augmentation code differs')
        self.records={row['step_zero_based']:row for row in captures['captures']}
        self.final=captures['final_sampler_result']
        s.audit['counterfactual']['pair_gates'].append({'gate':'initial_binding','pass':True,
            'seed':s.seed,'actual_noise_and_producer_clean_inputs_exact':True,
            'historical_full_processed_condition_tree':'unavailable; not claimed',
            'archived_embedding_tensor':embedding_record,
            'current_processed_condition_sha256':s.initial_condition['sha256'],
            'available_native_indices':sorted(self.records),'unavailable_native_indices':[i for i in range(20) if i not in self.records]})
    def branch(self,s,x,output,row):
        n,b=row['physical_index'],row['branch'];g={'gate':'native_prefix','physical_index':n,'branch':b,'first_on':self.first_on}
        if b!='native' or not self.native_comparable(n):
            g.update(status='not_applicable',reason='Full or permanently diverged actual trajectory')
        elif n not in self.records:g.update(status='unavailable_historical_capture',reason='no old checkpoint; does not postpone intervention')
        else:
            old=self.records[n]
            t.require(row['sigma']==old['sigma_video'] and row['sigma_next']==old['sigma_next_video'],'paired sigma mismatch')
            t.require(row['normalized_stream_signatures']==[old['video'],old['audio']],'available Native checkpoint mismatch')
            path=Path(self.case['parent_root'])/'audit/x0'/self.case['parent_run']/old['file']
            relative=str(path.relative_to(self.case['parent_root']))
            expected_file=t.read_json(t.ROOT/self.case['parent_file_inventory'])[relative]
            t.require(path.stat().st_size==expected_file['bytes'] and t.sha(path)==expected_file['sha256'],'historical capture file changed')
            saved=torch.load(path,map_location='cpu',weights_only=True);actual=torch.load(row['file'],map_location='cpu',weights_only=True)
            for key in ('video','audio'):
                t.require(readout.tensor_signature(saved[key])==old[key],'historical tensor changed')
                t.require(torch.equal(saved[key],actual[key]),'actual Native tensor differs')
            g.update(status='pass',tensor_equal=True,old_file=str(path),old_file_sha256=t.sha(path));self.done.add(n)
        s.audit['counterfactual']['pair_gates'].append(g)
    def decision(self,s,n,decision):
        if decision['chosen_full'] and self.first_on is None:
            self.first_on=n
            s.audit['counterfactual']['first_actual_full']=n
            s.audit['counterfactual']['old_native_future_eligibility']='permanently N/A; no reset on OFF'
    def finish(self,s):
        required={n for n in self.records if self.native_comparable(n)}
        t.require(required<=self.done,'missing eligible historical comparisons')
        s.audit['counterfactual']['native_preservation']={'zero_Full':self.first_on is None,'first_on':self.first_on,
            'status':'pending_final_exact_check' if self.first_on is None else 'divergent_controlled_trajectory',
            'case_role':'source28289 Elon Musk transfer; parent closure required',
            'prefix_evidence':'all20 historical captures available; current Native through firstON inclusive; future permanently N/A'}
