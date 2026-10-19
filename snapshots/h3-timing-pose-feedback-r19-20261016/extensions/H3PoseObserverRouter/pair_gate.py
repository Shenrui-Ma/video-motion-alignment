"""Fail closed if live prefixes differ from the completed R10/R12 trajectories."""
import copy
import torch
from . import transport as t
from .dependencies import readout

def canonical_condition(tree):
 out=copy.deepcopy(tree)
 for group in ('original','processed'):
  rows=out[group]['positive'];t.require(len(rows)==1 and 'uuid' in rows[0],'missing unique positive UUID')
  rows[0]['uuid']='<cross-run-positive-uuid>'
 return out

class HistoricalPairGate:
 def __init__(self):self.parents=None;self.done=set()
 def begin(self,s,noise):
  t.bindings();self.parents={}
  for key in ('r10','r12'):
   d=t.read_json(t.ROOT/f'configs/parent_{key}_audit.json');c=d['counterfactual']
   t.require(d['status']=='complete' and c['callback_count']==20,'historical run incomplete')
   t.require(s.seed==c['seed'] and s.grid.tolist()==c['full_grid'],'G1 seed/grid differs')
   t.require(readout.tensor_signature(noise)==c['initial_noise'] and s.reference_signature==c['reference'],'G1 noise/reference differs')
   t.require(canonical_condition(s.initial_condition['tree'])==canonical_condition(c['conditioning']['tree']),'G1 actual conditioning differs')
   self.parents[key]=c
  s.audit['counterfactual']['pair_gates'].append({'gate':'G1_initial','pass':True,'UUID_exceptions':['original.positive[0].uuid','processed.positive[0].uuid']})
 def branch(self,s,x,output,row):
  n,b=row['physical_index'],row['branch']
  if n>10:return
  actual=None
  for parent,c in self.parents.items():
   if n==10 and b=='full' and parent=='r12':continue
   matches=[r for r in c['branches'] if (r['physical_index'],r['branch'])==(n,b)]
   t.require(len(matches)==1,'missing historical branch')
   old=matches[0]
   for k in ('sigma','sigma_next','same_input','raw_stream_signatures','normalized_stream_signatures'):
    t.require(row[k]==old[k],f'G1 common {parent} {n}/{b} differs: '+k)
   # Exact tensors at the paired prefix checkpoints; SHA gates cover every native0..4 too.
   if n>=5:
    t.require(t.sha(old['file'])==old['file_sha256'],'historical endpoint file changed')
    saved=torch.load(old['file'],map_location='cpu',weights_only=True)
    if actual is None:actual=torch.load(row['file'],map_location='cpu',weights_only=True)
    t.require(all(torch.equal(actual[k],saved[k]) for k in ('video','audio')),f'G1 tensor equality failed {parent} {n}/{b}')
   if n in (6,10) and b=='native':
    oldinput=next(r for r in c['inputs'] if r['physical_index']==n)
    t.require(t.sha(oldinput['file'])==oldinput['file_sha256'],'historical raw input file changed')
    saved=torch.load(oldinput['file'],map_location='cpu',weights_only=True)['packed']
    t.require(torch.equal(x.detach().cpu(),saved),'G1 current packed input differs')
   self.done.add((parent,n,b))
  s.audit['counterfactual']['pair_gates'].append({'gate':'G1_common_endpoint','physical_index':n,'branch':b,'pass':True,'tensor_equal':n>=5})
 def finish(self,s):
  required={(p,n,b) for p in ('r10','r12') for n in range(11) for b in (('native','full') if 6<=n<=9 else ('native',))}
  t.require(required<=self.done,'incomplete historical prefix gates')
  t.require(any(g['gate']=='G2_current_native010' and g['pass'] for g in s.audit['counterfactual']['pair_gates']),'G2 bridge absent')
  if 10 in s.full_indices:t.require(('r10',10,'full') in self.done,'G3 Full10 replay absent')
