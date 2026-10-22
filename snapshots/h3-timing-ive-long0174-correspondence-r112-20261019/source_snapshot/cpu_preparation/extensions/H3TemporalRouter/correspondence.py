"""Frozen, paired reference correspondence and query-dependent Value transport.

No model weights or Q/K are changed. A bank is captured once, before the first
intervention, and shared by content hash across the two spatial-index arms.
"""
import hashlib
import json
import math
from pathlib import Path
import time

MODES = ('fixed_one_bin', 'matched_one_bin')
POLICY = {'descriptor': 'mean_per_head_value_cosine', 'tie_margin': 1e-6,
          'norm_epsilon': 1e-12, 'capture_step': 5,
          'matching': 'unique_mutual_nearest_adjacent_reference_frames',
          'reuse': 'freeze_each_block_for_steps_6_through_14',
          'acceptance_mask': 'shared_between_fixed_and_matched_arms'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def tensor_digest(tensor):
    import torch
    value = tensor.detach().cpu().contiguous()
    raw = value.view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(canonical({'shape':list(value.shape), 'dtype':str(value.dtype)}) + raw).hexdigest()


def evenly_spaced(count, maximum):
    return sorted({round(i*(count-1)/max(1,min(count,maximum)-1)) for i in range(min(count,maximum))})


def _geometry(values, frame_rows, valid_bins):
    if (values.ndim != 4 or values.shape[0] != 1 or type(frame_rows) is not int
            or frame_rows < 2 or values.shape[-2] % frame_rows or type(valid_bins) is not int
            or not 2 <= valid_bins <= values.shape[-2]//frame_rows):
        raise ValueError('one batch, complete reference frames, and at least two valid bins/positions required')
    if not values.is_floating_point(): raise ValueError('floating reference Values required')
    return {'batch':1, 'heads':values.shape[1], 'total_bins':values.shape[-2]//frame_rows,
            'valid_bins':valid_bins, 'frame_rows':frame_rows, 'head_dim':values.shape[-1]}


class FrozenBank:
    def __init__(self, forward, backward, metadata):
        import torch
        if forward.dtype not in (torch.int32,torch.int64) or backward.dtype not in (torch.int32,torch.int64):
            raise ValueError('integer correspondence indices required')
        self.forward = forward.detach().cpu().to(torch.int64).contiguous().clone()
        self.backward = backward.detach().cpu().to(torch.int64).contiguous().clone()
        self.metadata = json.loads(json.dumps(metadata))
        self._validate_structure()
        self.manifest = self._manifest()

    def _validate_structure(self):
        import torch
        g=self.metadata['geometry']; p=g['frame_rows']; shape=(g['valid_bins']-1,p)
        if tuple(self.forward.shape)!=shape or tuple(self.backward.shape)!=shape:
            raise ValueError('bank geometry differs')
        if g['batch']!=1 or not 2<=g['valid_bins']<=g['total_bins'] or g['heads']<1 or g['head_dim']<1:
            raise ValueError('invalid bank geometry')
        for x in (self.forward,self.backward):
            if not bool(((x>=-1)&(x<p)).all()):raise ValueError('bank index outside one spatial frame')
        pos=torch.arange(p)
        for f,b in zip(self.forward,self.backward):
            valid=f>=0
            if not torch.equal(b[f[valid]],pos[valid]):raise ValueError('forward bank lacks reciprocal inverse')
            valid=b>=0
            if not torch.equal(f[b[valid]],pos[valid]):raise ValueError('backward bank lacks reciprocal inverse')

    def _manifest(self):
        indices=tensor_digest(__import__('torch').stack((self.forward,self.backward)))
        masks=tensor_digest(__import__('torch').stack((self.forward>=0,self.backward>=0)))
        body={'schema':'r112-frozen-correspondence-bank-v1','metadata':self.metadata,
              'indices_sha256':indices,'masks_sha256':masks}
        return dict(body,bank_sha256=hashlib.sha256(canonical(body)).hexdigest())

    def verify(self):
        self._validate_structure()
        if self._manifest()!=self.manifest:raise ValueError('frozen correspondence bank was modified')
        return self.manifest

    def save(self, directory):
        import numpy as np
        self.verify();root=Path(directory);root.mkdir(parents=True,exist_ok=False)
        arrays=root/'indices.npz'
        np.savez_compressed(arrays,forward=self.forward.numpy().astype('<i4'),backward=self.backward.numpy().astype('<i4'))
        receipt=dict(self.manifest,storage={'file':'indices.npz','sha256':hashlib.sha256(arrays.read_bytes()).hexdigest()})
        (root/'bank.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
        return receipt

    @classmethod
    def load(cls,directory):
        import numpy as np
        import torch
        root=Path(directory);receipt=json.loads((root/'bank.json').read_text());arrays=root/'indices.npz'
        if receipt['storage']['file']!='indices.npz' or hashlib.sha256(arrays.read_bytes()).hexdigest()!=receipt['storage']['sha256']:
            raise ValueError('stored bank integrity failed')
        with np.load(arrays,allow_pickle=False) as data:
            if set(data.files)!={'forward','backward'}:raise ValueError('unexpected bank arrays')
            bank=cls(torch.from_numpy(data['forward'].copy()),torch.from_numpy(data['backward'].copy()),receipt['metadata'])
        if bank.manifest!={k:v for k,v in receipt.items() if k!='storage'}:raise ValueError('stored bank manifest differs')
        return bank


def build_bank(values, *, frame_rows, valid_bins, block, source_step=5):
    import torch
    start=time.perf_counter();g=_geometry(values,frame_rows,valid_bins)
    if source_step!=POLICY['capture_step'] or type(block) is not int or not 0<=block<50:
        raise ValueError('bank must come from the registered common prefix step/block')
    if not bool(torch.isfinite(values).all()):raise ValueError('nonfinite reference Values')
    work=torch.float64 if values.dtype==torch.float64 else torch.float32
    frames=values.reshape(1,g['heads'],g['total_bins'],frame_rows,g['head_dim'])[0]
    sampled=frames[evenly_spaced(g['heads'],8)][:,evenly_spaced(g['total_bins'],8)][:,:,evenly_spaced(frame_rows,8)][:,:,:,evenly_spaced(g['head_dim'],16)]
    source_hash=tensor_digest(sampled)
    sample_pairs=set(evenly_spaced(valid_bins-1,5));sample_positions=evenly_spaced(frame_rows,6)
    def desc(t):
        f=frames[:,t].to(work);norm=f.square().sum(-1).sqrt()
        valid=(norm>POLICY['norm_epsilon']).all(0)
        x=(f/norm.clamp_min(POLICY['norm_epsilon']).unsqueeze(-1)).permute(1,0,2).reshape(frame_rows,-1)
        return x,valid
    fwd=[];bwd=[];stats=[];samples=[];left,left_valid=desc(0)
    positions=torch.arange(frame_rows,device=values.device)
    for t in range(valid_bins-1):
        right,right_valid=desc(t+1)
        scores=(left@right.T)/g['heads']
        scores.masked_fill_(~(left_valid[:,None]&right_valid[None,:]),-torch.inf)
        top,fi=scores.topk(2,dim=1);back,bi=scores.topk(2,dim=0)
        forward=fi[:,0];backward=bi[0]
        fg=top[:,0]-top[:,1];bg=back[0]-back[1]
        fm=(fg>POLICY['tie_margin'])&(bg[forward]>POLICY['tie_margin'])&(backward[forward]==positions)&left_valid&right_valid[forward]
        bm=(bg>POLICY['tie_margin'])&(fg[backward]>POLICY['tie_margin'])&(forward[backward]==positions)&right_valid&left_valid[backward]
        fwd.append(torch.where(fm,forward,-torch.ones_like(forward)))
        bwd.append(torch.where(bm,backward,-torch.ones_like(backward)))
        count=fm.sum();den=count.clamp_min(1);chosen=torch.where(fm,top[:,0],0.)
        # Spatial displacement is reported in token-index units here; rows/cols
        # are saved in geometry separately by the producer for visual inspection.
        displacement=(forward-positions).abs().to(work)
        stats.append(torch.stack((count.to(work),chosen.sum()/den,torch.where(fm,fg,0.).sum()/den,
                                  torch.where(fm,displacement,0.).sum()/den,
                                  torch.where(fm,displacement,0.).max())))
        if t in sample_pairs:
            for s in sample_positions:
                # Invalid entries use finite sentinels plus an explicit valid bit.
                top_score=torch.where(torch.isfinite(top[s,0]),top[s,0],torch.zeros_like(top[s,0]))
                margin=torch.where(torch.isfinite(fg[s]),fg[s],torch.zeros_like(fg[s]))
                samples.append(torch.stack((torch.tensor(float(t),device=values.device,dtype=work),
                    torch.tensor(float(s),device=values.device,dtype=work),forward[s].to(work),fm[s].to(work),top_score,margin)))
        left,left_valid=right,right_valid
    forward=torch.stack(fwd).cpu();backward=torch.stack(bwd).cpu()
    metadata={'geometry':g,'source_step':source_step,'block':block,'policy':POLICY,
              'source_value_sample_sha256':source_hash,'source_value_dtype':str(values.dtype),
              'numeric_context':{'torch_version':str(torch.__version__),'device':str(values.device),
                                 'float32_matmul_precision':torch.get_float32_matmul_precision(),
                                 'cuda_matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32},
              'sample_policy':{'heads':evenly_spaced(g['heads'],8),'times':evenly_spaced(g['total_bins'],8),
                               'positions':evenly_spaced(frame_rows,8),'channels':evenly_spaced(g['head_dim'],16)}}
    bank=FrozenBank(forward,backward,metadata)
    audit={'bank_sha256':bank.manifest['bank_sha256'],'capture_wall_seconds':time.perf_counter()-start,
           'accepted_forward_count':int((forward>=0).sum()),'unmatched_forward_count':int((forward<0).sum()),
           'unmatched_forward_fraction':float((forward<0).double().mean()),
           'pair_stat_columns':['accepted','mean_cosine_accepted','mean_margin_accepted','mean_abs_flat_index_displacement','max_abs_flat_index_displacement'],
           'pair_stats':torch.stack(stats).cpu().tolist(),
           'sample_columns':['source_bin','source_position','candidate_target_position','accepted','cosine_or_zero','margin_or_zero'],
           'samples':torch.stack(samples).cpu().tolist()}
    return bank,audit


def verify_common_prefix(current_manifest,paired_manifest):
    """Read the six actual x0 tensor files before either arm can diverge."""
    import torch
    def read(path):
        path=Path(path);m=json.loads(path.read_text());records=m['captures'][:6]
        if [r['step_zero_based'] for r in records]!=list(range(6)):
            raise ValueError('six common-prefix x0 captures required')
        actual=[]
        for row in records:
            name=row['file']
            if name!=f"x0_step{row['step_zero_based']:03d}.pt":raise ValueError('unexpected prefix capture filename')
            payload=torch.load(path.parent/name,map_location='cpu',weights_only=True)
            signatures={}
            for stream in ('video','audio'):
                value=payload[stream].detach().cpu().contiguous()
                sig={'shape':list(value.shape),'dtype':str(value.dtype),'bytes':value.numel()*value.element_size(),
                     'sha256':hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}
                if sig!=row[stream]:raise ValueError('actual prefix x0 differs from manifest')
                signatures[stream]=sig
            actual.append(signatures)
        header={key:m[key] for key in ('geometry','target_latent_shapes','sigmas_video','sampler','seed','audio_scale','video_latent_scale_factor','normalization_stage','noise')}
        return {'header':header,'actual_first_six':actual}
    current=read(current_manifest);paired=read(paired_manifest)
    if current!=paired:raise ValueError('paired common-prefix trajectory differs before intervention')
    return {'passed':True,'prefix_steps':list(range(6)),'signature_sha256':hashlib.sha256(canonical(current)).hexdigest(),
            'actual_tensor_files_verified':12,'scope':'video/audio x0, initial noise signature, schedule and geometry'}


def transport_maps(bank,mode,device):
    import torch
    bank.verify()
    if mode not in MODES:raise ValueError('unknown one-bin spatial arm')
    g=bank.metadata['geometry'];t=g['total_bins'];p=g['frame_rows'];valid=g['valid_bins']
    identity=torch.arange(t*p,dtype=torch.int64).reshape(t,p)
    forward=identity.clone();backward=identity.clone();space=torch.arange(p).expand(valid-1,p)
    f=bank.forward;b=bank.backward
    fspace=space if mode=='fixed_one_bin' else f
    bspace=space if mode=='fixed_one_bin' else b
    forward[:valid-1]=torch.where(f>=0,torch.arange(1,valid)[:,None]*p+fspace,identity[:valid-1])
    backward[1:valid]=torch.where(b>=0,torch.arange(valid-1)[:,None]*p+bspace,identity[1:valid])
    return forward.to(device),backward.to(device),identity.to(device)


def one_bin_attention(q_event,k_ref,v_ref,*,latent_lo,frame_rows,bank,mode,attention,diagnostics=None):
    import torch
    g=bank.metadata['geometry'];actual=_geometry(v_ref,frame_rows,g['valid_bins'])
    if actual!=g or k_ref.shape!=v_ref.shape or q_event.ndim!=4 or q_event.shape[:2]!=v_ref.shape[:2] or q_event.shape[-1]!=v_ref.shape[-1]:
        raise ValueError('bank/reference/query shape mismatch')
    if (type(latent_lo) is not int or q_event.shape[-2]%frame_rows or q_event.shape[-2]<1
            or not 0<=latent_lo<latent_lo+q_event.shape[-2]//frame_rows<=g['valid_bins']):
        raise ValueError('query interval exceeds valid reference bins')
    start=time.perf_counter();events=None
    if v_ref.device.type=='cuda':
        events=(torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True));events[0].record()
    forward,backward,identity=transport_maps(bank,mode,v_ref.device)
    times=torch.arange(g['total_bins'],device=v_ref.device)[:,None]
    out=torch.empty_like(q_event)
    for local in range(q_event.shape[-2]//frame_rows):
        tau=latent_lo+local
        index=torch.where(times<tau,forward,torch.where(times>tau,backward,identity)).reshape(1,1,-1,1)
        transported=torch.gather(v_ref,2,index.expand_as(v_ref))
        value,_=attention(q_event[:,:,local*frame_rows:(local+1)*frame_rows],k_ref,transported)
        out[:,:,local*frame_rows:(local+1)*frame_rows].copy_(value)
        del transported,value
    if events:events[1].record()
    if diagnostics is not None:diagnostics.append({'bank_sha256':bank.manifest['bank_sha256'],
        'mode':mode,'enqueue_wall_seconds':time.perf_counter()-start,'cuda_events':events})
    return out


def validate_packed_plan(plan,bank,sequence_length):
    """Reject accidental routing through text, character image or audio spans."""
    g=bank.metadata['geometry'];p=g['frame_rows']
    ra,rb=plan['reference_video_segment'];qa,qb=plan['query_interval_half_open'];ta,tb=plan['target_video_segment'];lo,hi=plan['latent_interval_half_open']
    if (plan['seq_len']!=sequence_length or plan['frame_rows']!=p
            or rb-ra!=g['total_bins']*p or tb-ta!=g['total_bins']*p
            or (qa,qb)!=(ta+lo*p,ta+hi*p) or not 0<=lo<hi<=g['valid_bins']
            or not 0<=ra<rb<=ta<tb<=sequence_length):raise ValueError('packed time/modality boundary mismatch')
    segments=[tuple(x) for x in plan['segments']];cursor=0
    for a,b,kind in segments:
        if a!=cursor or b<=a or kind not in ('text','ref_img','ref_audio','audio','video'):
            raise ValueError('noncontiguous/unsupported packed segments')
        cursor=b
    if cursor!=sequence_length or (ra,rb,'ref_img') not in segments or (ta,tb,'video') not in segments:
        raise ValueError('reference and canvas segments must match exactly')
    for a,b in plan['reference_image_segments']:
        if max(a,ra)<min(b,rb):raise ValueError('character image entered reference-video transport')


def sample_support_mass(query,keys,mass,bank,*,latent_lo,frame_rows):
    """Original conditional/full attention on accepted keys, at fixed samples."""
    import torch
    bank.verify();g=bank.metadata['geometry'];times=torch.arange(g['total_bins'],device=query.device)[:,None]
    h=evenly_spaced(query.shape[1],8);rows=evenly_spaced(query.shape[2],12)
    selected=query[:,h][:,:,rows].float();reference=keys[:,h].float()
    probabilities=(selected@reference.transpose(-1,-2)/math.sqrt(query.shape[-1])).softmax(-1)
    fm=torch.zeros((g['total_bins'],frame_rows),device=query.device,dtype=torch.bool)
    bm=torch.zeros_like(fm);fm[:g['valid_bins']-1]=bank.forward.to(query.device)>=0;bm[1:g['valid_bins']]=bank.backward.to(query.device)>=0
    masks=[]
    for qi in rows:
        tau=latent_lo+qi//frame_rows
        masks.append(((times<tau)&fm | (times>tau)&bm).flatten())
    support=torch.stack(masks)
    conditional=(probabilities*support[None,None]).sum(-1)
    full=conditional*mass[:,h][:,:,rows].float()
    result=torch.stack((conditional,full),-1).cpu().tolist()[0]
    return {'scope':'up to8heads x12 uniformly selected query positions, original QK; accepted keys can be foreground or background',
            'records':[{'head':head,'query_latent_bin':latent_lo+qi//frame_rows,'query_position':qi%frame_rows,
                        'accepted_reference_conditional_mass':result[j][i][0],'accepted_full_attention_mass':result[j][i][1]}
                       for j,head in enumerate(h) for i,qi in enumerate(rows)]}


def sample_bank_similarity(values,bank):
    """Observe current Value similarity at frozen matches without updating them."""
    import torch
    g=bank.metadata['geometry'];p=g['frame_rows'];v=values.reshape(1,g['heads'],g['total_bins'],p,g['head_dim'])[0]
    samples=[]
    for t in evenly_spaced(g['valid_bins']-1,5):
        for s in evenly_spaced(p,6):
            j=int(bank.forward[t,s])
            if j<0:continue
            a=v[:,t,s].float();b=v[:,t+1,j].float();same=v[:,t+1,s].float()
            score=torch.nn.functional.cosine_similarity(a,b,dim=-1).mean()
            coordinate=torch.nn.functional.cosine_similarity(a,same,dim=-1).mean()
            samples.append((t,s,j,torch.stack((score,coordinate))))
    if not samples:return {'scope':'no accepted sampled matches','records':[]}
    scores=torch.stack([x[3] for x in samples]).cpu().tolist()
    return {'scope':'frozen adjacent matches, current Values; cosine is a correspondence diagnostic, not identity truth',
            'records':[{'source_bin':t,'source_position':s,'target_position':j,'current_match_cosine':x[0],
                        'current_same_coordinate_cosine':x[1]} for (t,s,j,_),x in zip(samples,scores)]}


class BankStore:
    def __init__(self,root,*,paired_root=None,num_blocks=50,valid_bins=43,spatial_grid=None):
        self.root=Path(root);self.paired_root=Path(paired_root) if paired_root else None
        if not self.root.is_absolute() or (self.paired_root and not self.paired_root.is_absolute()):raise ValueError('absolute bank roots required')
        if self.root.exists():raise FileExistsError(self.root)
        self.root.mkdir(parents=True);self.banks={};self.audits={};self.num_blocks=num_blocks;self.valid_bins=valid_bins;self.spatial_grid=spatial_grid

    def capture(self,block,step,values,frame_rows):
        if block in self.banks or not 0<=block<self.num_blocks:raise ValueError('duplicate/unregistered bank block')
        bank,audit=build_bank(values,frame_rows=frame_rows,valid_bins=self.valid_bins,block=block,source_step=step)
        if self.spatial_grid is not None:
            if (len(self.spatial_grid)!=2 or any(type(x) is not int or x<1 for x in self.spatial_grid)
                    or math.prod(self.spatial_grid)!=frame_rows):raise ValueError('spatial grid mismatch')
            metadata=dict(bank.metadata,spatial_grid=self.spatial_grid)
            bank=FrozenBank(bank.forward,bank.backward,metadata);audit['bank_sha256']=bank.manifest['bank_sha256']
        if self.paired_root:
            other=FrozenBank.load(self.paired_root/f'block_{block:02d}')
            if bank.manifest!=other.manifest:raise ValueError('paired banks differ before intervention')
        bank.save(self.root/f'block_{block:02d}');self.banks[block]=bank;self.audits[block]=audit
        return audit

    def get(self,block,step):
        if not 6<=step<15 or set(self.banks)!=set(range(self.num_blocks)):
            raise ValueError('complete frozen prefix bank required before intervention')
        bank=self.banks[block];bank.verify()
        return bank

    def receipt(self):
        if set(self.banks)!=set(range(self.num_blocks)):raise ValueError('incomplete bank collection')
        rows={str(b):self.banks[b].verify()['bank_sha256'] for b in range(self.num_blocks)}
        return {'schema':'r112-bank-collection-v1','blocks':rows,'collection_sha256':hashlib.sha256(canonical(rows)).hexdigest(),
                'paired_collection_required':bool(self.paired_root),'capture_step':5}
