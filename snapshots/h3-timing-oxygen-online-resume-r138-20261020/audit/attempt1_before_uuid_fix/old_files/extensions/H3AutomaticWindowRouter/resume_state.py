"""Restore exact R133 state9 and continue its unchanged Euler/controller trajectory.

Prefix callbacks are archival replay. They execute no DiT or observer. The old
unfinished step9 prediction is counted as spent work and is checked on recompute.
"""
import copy
import json
import os
from pathlib import Path

import torch

from . import transport as t
from .dependencies import readout


def packed_endpoint(record):
    path=Path(record['file'])
    t.require(t.sha(path)==record['file_sha256'],'resume endpoint bytes changed')
    value=torch.load(path,map_location='cpu',weights_only=True)
    t.require([readout.tensor_signature(value[k]) for k in ('video','audio')]
              ==record['normalized_stream_signatures'],'resume endpoint tensor changed')
    return torch.cat([value['video'].reshape(1,1,-1),
                      (value['audio']*4).reshape(1,1,-1)],dim=-1)


def euler_update(x,denoised,grid,index):
    return x+((x-denoised)/grid[index].reshape(*([1]*x.ndim)))*(grid[index+1]-grid[index])


class ResumeState:
    def __init__(self,state):
        self.state=state
        self.config=t.read_json(t.ROOT/'configs/RESUME.json')
        self.start=self.config['start_physical_index']
        t.require(self.start==9,'this recovery binds the observed state9 only')
        for rel,item in self.config['source_files'].items():
            p=Path(self.config['source_root'])/rel
            t.require(p.stat().st_size==item['bytes'] and t.sha(p)==item['sha256'],
                      'resume source bytes changed: '+rel)
        self.old=t.read_json(self.config['source_audit'])
        oldc=self.old['counterfactual']
        t.require(self.old['status']=='failed' and len(oldc['steps'])==self.start,
                  'resume requires the preserved interrupted trajectory')
        self.old_branches={(b['physical_index'],b['branch']):b for b in oldc['branches']}
        t.require(len(oldc['branches'])==13,'old spent prediction count differs')
        self.state9=torch.load(self.config['state_file'],map_location='cpu',weights_only=True)['packed']
        t.require(readout.tensor_signature(self.state9)['sha256']==self.config['state_packed_sha256'],
                  'restored state9 differs')
        t.require(readout.tensor_signature(self.state9)==self.old_branches[9,'native']['same_input'],
                  'restored state9 differs from recorded actual input')
        self.replayed_callbacks=[]
        self.first_restored_native_checked=False

    def hydrate(self):
        s=self.state;oldc=self.old['counterfactual'];fresh=s.audit['counterfactual']
        t.require(s.seed==oldc['seed'] and s.grid.tolist()==oldc['full_grid'],'resume seed/grid changed')
        t.require(s.initial_condition==oldc['conditioning'],'resume processed conditioning changed')
        t.require(s.reference_signature==oldc['reference'],'resume reference changed')
        t.require(fresh['initial_noise']==oldc['initial_noise'],'resume actual AV noise changed')
        self.new_initial_binding=copy.deepcopy(fresh['pair_gates'][0])
        prefix=copy.copy(oldc)
        prefix['steps']=copy.deepcopy(oldc['steps'])
        prefix['branches']=copy.deepcopy([b for b in oldc['branches'] if b['physical_index']<self.start])
        prefix['measurements']=oldc['measurements'][:self.start]
        prefix['inputs']=copy.deepcopy(oldc['inputs'])
        prefix['pair_gates']=[copy.deepcopy(g) for g in oldc['pair_gates']
                              if g.get('physical_index',-1)<self.start]
        prefix['full_physical_indices']=list(oldc['full_physical_indices'])
        prefix['input_archive_indices']=sorted({r['physical_index'] for r in oldc['inputs']}|set(range(self.start,20)))
        prefix['new_generation_input_archive_indices']=list(range(self.start,20))
        prefix['observer_protocol_sha256']=t.PROTOCOL_SHA
        prefix['frozen_scientific_protocol_sha256']=t.PROTOCOL_SHA
        prefix['counter_scope']='logical trajectory across explicitly bound process generations'
        prefix['resume']={'schema':'r138-resume-lineage-v1','config_sha256':t.sha(t.ROOT/'configs/RESUME.json'),
            'source_run':self.config['source_run'],'source_audit':self.config['source_audit'],
            'source_release':self.config['source_release'],'start_physical_index':self.start,
            'inherited_complete_updates':9,'inherited_logical_model_nfe':12,
            'old_actual_executed_model_nfe':13,'discarded_old_execution':self.old_branches[9,'native'],
            'reconstruction_model_nfe':0,'initial_rng_bytes_available':False,
            'new_initial_binding':self.new_initial_binding,'replayed_archival_callbacks':self.replayed_callbacks,
            'actual_new_model_nfe':0,'actual_new_euler_updates':0,
            'state9_signature':readout.tensor_signature(self.state9)}
        # Archive the immutable endpoint entities under this root by hardlink.
        mapping={}
        for b in prefix['branches']:
            oldpath=Path(b['file']);newpath=s.snapshots/oldpath.name
            t.require(t.sha(oldpath)==b['file_sha256'],'inherited endpoint changed')
            os.link(oldpath,newpath)
            b['file']=str(newpath);b['execution_generation']='R133'
            b['original_file']=str(oldpath);mapping[str(oldpath)]=str(newpath)
        for step in prefix['steps']:
            step['chosen_file']=mapping[step['chosen_file']]
            step['execution_generation']='R133'
        for index,m in enumerate(prefix['measurements']):
            decision=s.controller.select(index,m)
            actual=prefix['steps'][index]['decision']
            t.require(all(actual[k]==v for k,v in decision.items()),'old controller state replay differs')
        s.full_indices=prefix['full_physical_indices']
        s.callback_count=self.start;s.previous_choice=prefix['steps'][-1]['selected_branch']=='full'
        s.pair_gate.first_on=min(s.full_indices)
        s.pair_gate.done={g['physical_index'] for g in prefix['pair_gates']
                          if g.get('gate')=='native_prefix' and g.get('status')=='pass'}
        s.audit['counterfactual']=prefix
        s.audit['forward_counter_scope']='logical forwards including12 inherited R133; actual generation counts in counterfactual.resume'
        nfe=len(prefix['branches']);s.forward_index=nfe-1;s.next_block=0
        for field in ('calls_by_forward','routed_by_forward','forward_summaries'):
            s.audit[field]=copy.deepcopy(self.old[field][:nfe])
        s.audit.update(started_calls=50*nfe,completed_calls=50*nfe,native_override_calls=50*nfe,
            routed_calls=50*len(s.full_indices),completed_forward_calls=nfe,
            calls_by_block=[nfe]*50,routed_by_block=[len(s.full_indices)]*50,
            diagnostic_calls=0,status='sampling',last_completed_forward_index=nfe-1)
        for field in ('temporal_readouts','component_readouts','native_feature_captures'):
            s.audit[field]=[copy.deepcopy(x) for x in self.old.get(field,[])
                            if x.get('forward_index',nfe)<nfe]
        s.write()

    def replay_callback(self,index,x0,x,total):
        t.require(total==20 and index==len(self.replayed_callbacks) and index<self.start,
                  'archival callback order differs')
        oldc=self.old['counterfactual'];step=oldc['steps'][index]
        b=self.old_branches[index,step['selected_branch']]
        t.require(readout.tensor_signature(x)==self.old_branches[index,'native']['same_input'],
                  'archival callback noisy state changed')
        t.require([readout.tensor_signature(v) for v in self.state.raw(x0)]==b['raw_stream_signatures'],
                  'archival callback chosen endpoint changed')
        self.replayed_callbacks.append(index)

    def sampler_function(self,original):
        def sample_euler(model,x,sigmas,extra_args=None,callback=None,disable=None,**options):
            t.require(options.get('s_churn',0)==0,'recovery requires zero churn')
            cpu=x.detach().cpu().clone();grid=sigmas.detach().cpu()
            for index in range(self.start):
                b=self.old_branches[index,self.old['counterfactual']['steps'][index]['selected_branch']]
                t.require(readout.tensor_signature(cpu)==self.old_branches[index,'native']['same_input'],
                          'prefix Euler reconstruction differs at '+str(index))
                den=packed_endpoint(b)
                callback({'x':cpu,'i':index,'sigma':grid[index],'sigma_hat':grid[index],'denoised':den})
                cpu=euler_update(cpu,den,grid,index)
            t.require(torch.equal(cpu,self.state9),'full prefix reconstruction differs from exact state9')
            t.require(self.replayed_callbacks==list(range(self.start)),'prefix callbacks missing')
            self.state.audit['counterfactual']['resume']['prefix_reconstruction_exact']=True
            def shifted(value):
                value=dict(value);value['i']+=self.start
                return callback(value)
            return original(model,self.state9.to(device=x.device),sigmas[self.start:],
                            extra_args=extra_args,callback=shifted,disable=disable,**options)
        return sample_euler

    def check_native(self,row):
        if row['physical_index']==self.start and row['branch']=='native':
            old=self.old_branches[self.start,'native']
            t.require(row['same_input']==old['same_input'] and
                      row['normalized_stream_signatures']==old['normalized_stream_signatures'],
                      'first restored Native prediction differs from actual interrupted step9')
            self.first_restored_native_checked=True
            self.state.audit['counterfactual']['resume']['first_restored_native_exact']=True

    def finish(self):
        c=self.state.audit['counterfactual'];r=c['resume']
        t.require(self.first_restored_native_checked,'missing restored-boundary model check')
        r['actual_new_model_nfe']=len([b for b in c['branches'] if b['physical_index']>=self.start])
        r['actual_new_euler_updates']=20-self.start
        r['actual_all_generations_model_nfe']=r['old_actual_executed_model_nfe']+r['actual_new_model_nfe']
        r['logical_model_nfe']=len(c['branches'])
        r['logical_euler_updates']=20
        t.require(r['actual_all_generations_model_nfe']==r['logical_model_nfe']+1,
                  'interrupted step9 cost accounting differs')
