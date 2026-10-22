"""Staged fixed-budget semantic pixel phase × timestamp phase diagnostic.

No model/attention patch; native preprocessing and real CLIP tokenization execute.
Only this node's reference-video semantic presentation may change. Fail closed
against the frozen source05 seed1 layout, dense input/latent and paired noise.
"""
from pathlib import Path
import hashlib
import json
import torch
from .audited_event import (Store, VAEProxy, CachedNoise, sampling_plan, safe_id,
                            atomic_json, tensor_info, token_ledger)

REMOTE_ROOT = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016_semantic0')
ZERO_ID = 's05_semantic_a0_p0_t0_condition'
BASE_CONDITION = '05_sam_1312x736_shared_v3_conditioning.json'
BASE_NOISE = 's05_full_seed1_native_noise.json'
PINNED_BASELINE_SHA = {'05_sam_1312x736_shared_v3_conditioning.json': 'ce14565bc7279b3a75ef9f5239f8e264049e8dc02cdc4e1e4e59d3dbe51528a3', 's05_full_seed1_native_noise.json': 'd23d4260b878c5cb0aaaa4416487522899c69989673743c2c44c2d0edb77b47f'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core_digest():
    return {p.name: digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def task_path(value, mkdir=False):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('semantic audit path must be absolute')
    path = path.resolve()
    if not path.is_relative_to(REMOTE_ROOT.resolve()) or path == REMOTE_ROOT.resolve():
        raise ValueError('semantic path must be an exact descendant of the pinned semantic0 root')
    if mkdir:
        path.mkdir(parents=True, exist_ok=True)
    return path


def identity(value):
    if isinstance(value, dict):
        return {k: identity(v) for k,v in value.items() if k != 'tensor_file'}
    if isinstance(value, (tuple, list)):
        return [identity(v) for v in value]
    return value


def clock_plan(frame_count, pixel_phase_frames=0, label_phase_frames=0):
    if frame_count != 141 or type(pixel_phase_frames) is not int or type(label_phase_frames) is not int:
        raise ValueError('this fixed-budget pilot requires exactly 141 prepared frames and integer phases')
    if pixel_phase_frames not in (0,6) or label_phase_frames not in (0,6):
        raise ValueError('pre-registered phases are only 0 and 6 frames')
    pixels = sampling_plan(frame_count, 2, pixel_phase_frames)
    labels = sampling_plan(frame_count, 2, label_phase_frames)
    if len(pixels['sample_indices']) != 12 or len(labels['temporal_blocks']) != 6:
        raise ValueError('12 samples / 6 blocks invariant failed; padding is forbidden')
    return {'source_fps':24, 'semantic_fps':2, 'pixel_phase_frames':pixel_phase_frames,
            'label_phase_frames':label_phase_frames,
            'sample_indices':pixels['sample_indices'],
            'actual_source_timestamps_seconds':pixels['sample_timestamps_seconds'],
            'presented_timestamps_seconds':labels['sample_timestamps_seconds'],
            'physical_pixel_phase_seconds':pixel_phase_frames/24.,
            'rendered_labels':[b['rendered_timestamp'] for b in labels['temporal_blocks']],
            'physical_blocks':pixels['temporal_blocks'], 'label_blocks':labels['temporal_blocks'],
            'note':'P6 changes sampled content by 0.25 s; T6 rendered labels differ from T0 by 0.3 s.'}


class ClipProxy:
    def __init__(self, native, vae, store, pixel_phase_frames=0, label_phase_frames=0):
        self.native, self.vae, self.store = native, vae, store
        self.pixel_phase, self.label_phase = pixel_phase_frames, label_phase_frames
        self.presentation, self.tokens, self.tokenize_calls = [], None, 0
        self.timestamp_lexical_tokens = None

    def __getattr__(self, name):
        return getattr(self.native, name)

    def tokenize(self, prompt, **kwargs):
        self.tokenize_calls += 1
        if self.tokenize_calls != 1:
            raise ValueError('exactly one native tokenization call required')
        items = kwargs['minimax_ref_items']
        if [i['type'] for i in items] != ['image','video']:
            raise ValueError('fixed pilot requires one identity image followed by one silent video')
        updated = []
        for item in items:
            if item['type'] != 'video':
                updated.append(item)
                self.presentation.append(token_ledger(item, self.store))
                continue
            frames = self.vae.video_frames
            if frames is None:
                raise ValueError('native VAE must receive dense frames before tokenization')
            plan = clock_plan(len(frames), self.pixel_phase, self.label_phase)
            native_plan = sampling_plan(len(frames), 2, 0)
            if not torch.equal(item['data'], frames[native_plan['sample_indices']]) or item['timestamps'] != native_plan['sample_timestamps_seconds']:
                raise ValueError('native semantic presentation changed; re-audit required')
            if self.pixel_phase == self.label_phase == 0:
                modified = item  # Exact native identity pass-through, including tensor objects.
            else:
                modified = dict(item)
                if self.pixel_phase:
                    modified['data'] = frames[plan['sample_indices']]
                if self.label_phase:
                    modified['timestamps'] = plan['presented_timestamps_seconds']
            updated.append(modified)
            self.presentation.append({'type':'video', 'sampling':plan,
                'actual_sampled_frames':self.store.tensor(modified['data'])})
        if self.pixel_phase or self.label_phase:
            kwargs = dict(kwargs, minimax_ref_items=updated)
        # CPU lexical probes use the real native tokenizer, not hand-written BPE IDs.
        # They do not execute Qwen or alter the actual presentation.
        base_labels = clock_plan(141,0,0)['rendered_labels']
        actual_labels = clock_plan(141,self.pixel_phase,self.label_phase)['rendered_labels']
        lexical = {}
        for label in dict.fromkeys(base_labels + actual_labels):
            ledger = token_ledger(self.native.tokenize(label), self.store)
            entries = ledger['qwen3vl_32b'][0]
            if any(not isinstance(e[0],int) for e in entries):
                raise ValueError('timestamp lexical tokenization unexpectedly includes vision')
            lexical[label] = entries
        self.timestamp_lexical_tokens = {'baseline_labels':base_labels,'presented_labels':actual_labels,'tokens':lexical}
        tokens = self.native.tokenize(prompt, **kwargs)
        self.tokens = token_ledger(tokens, self.store)
        return tokens


def token_structure(tokens):
    """Text ids may differ; token types/weights/vision sizes and boundaries may not."""
    batches = tokens.get('qwen3vl_32b')
    if not isinstance(batches,list) or len(batches) != 1:
        raise ValueError('one qwen3vl_32b token batch required')
    out, videos, images = [], 0, 0
    for entry in batches[0]:
        value, weight, *rest = entry
        if isinstance(value,dict):
            data = value['data']['tensor']
            video = bool(value.get('minimax_video_block',False))
            videos += int(video); images += int(not video)
            out.append(['vision', value['type'], value.get('original_type'), video,
                        data['shape'],data['dtype'],weight,rest])
        else:
            # Preserve all native boundary token values, but not ordinary text IDs.
            out.append(['token',value if value in (151652,151653) else None,weight,rest])
    if videos != 6 or images != 1:
        raise ValueError('actual tokenizer must emit 6 video vision entries and one identity entry')
    return out


def verify_timestamp_only_text(actual,baseline,lexical):
    a=actual['qwen3vl_32b'][0]; b=baseline['qwen3vl_32b'][0]
    if len(a)!=len(b):
        raise ValueError('timestamp edit changed pre-expansion length')
    video=[i for i,e in enumerate(b) if isinstance(e[0],dict) and e[0].get('minimax_video_block',False)]
    allowed=set()
    if len(video)!=6:
        raise ValueError('baseline must have six video blocks')
    for idx,(i,before,after) in enumerate(zip(video,lexical['baseline_labels'],lexical['presented_labels'])):
        old=lexical['tokens'][before]; new=lexical['tokens'][after]
        if len(old)!=len(new):
            raise ValueError('real timestamp BPE length changed')
        lo,hi=i-1-len(old),i-1
        if b[lo:hi]!=old or a[lo:hi]!=new:
            raise ValueError('actual timestamp token span disagrees with native lexical tokens')
        allowed.update(range(lo,hi))
    for i,(left,right) in enumerate(zip(a,b)):
        if i not in allowed and not isinstance(left[0],dict) and left!=right:
            raise ValueError('non-timestamp text tokens changed')
    return {'timestamp_spans':6,'non_timestamp_text_ids_equal':True}


def verify_against_baseline(manifest, baseline, layout, pixel_phase, label_phase):
    for key in ('prompt','input_video','native_vae_calls','token_tags','target_latent_shapes','packed_layout'):
        if identity(manifest[key]) != identity(baseline[key]):
            raise ValueError('frozen baseline invariant failed: '+key)
    if manifest['conditioning_embedding']['shape'] != baseline['conditioning_embedding']['shape']:
        raise ValueError('expanded conditioning token count/width changed')
    if manifest['conditioning_embedding']['dtype'] != baseline['conditioning_embedding']['dtype']:
        raise ValueError('conditioning dtype changed')
    if token_structure(manifest['tokenization_before_vision_expansion']) != token_structure(baseline['tokenization_before_vision_expansion']):
        raise ValueError('timestamp change altered actual token topology/vision blocks')
    # Compare actual position coordinates rather than inferring a common origin.
    segments = layout.segments
    ref = [s for s in segments if s[2] == 'ref_img'][-1]
    target = next(s for s in segments if s[2] == 'video')
    q = layout.position_ids[target[0]:target[1]]
    k = layout.position_ids[ref[0]:ref[1]]
    delta = q[:,0]-k[:,0]
    if q.shape != k.shape or not torch.equal(q[:,1:],k[:,1:]) or not torch.all(delta == 235.).item():
        raise ValueError('actual dense ref/target layout no longer has identical spatial coordinates and native gap235')
    if pixel_phase == 0:
        expected = next(p for p in baseline['qwen_presentation'] if p['type']=='video')['actual_sampled_frames']
        actual = next(p for p in manifest['qwen_presentation'] if p['type']=='video')['actual_sampled_frames']
        if identity(expected) != identity(actual):
            raise ValueError('P0 semantic vision pixels changed')
    if pixel_phase == label_phase == 0:
        for key in ('conditioning_embedding','tokenization_before_vision_expansion'):
            if identity(manifest[key]) != identity(baseline[key]):
                raise ValueError('A0 exact zero-equivalence failed: '+key)
    return {'baseline_invariants_passed':True, 'reference_target_time_gap':235.,
            'checked_position_rows':int(len(delta)), 'actual_video_blocks':6,
            'expanded_tokens':manifest['conditioning_embedding']['shape'][1],
            'zero_embedding_and_tokens_bitwise':pixel_phase == label_phase == 0}


def read_baselines():
    cp = task_path(REMOTE_ROOT/'baseline'/BASE_CONDITION)
    np = task_path(REMOTE_ROOT/'baseline'/BASE_NOISE)
    if digest(cp) != PINNED_BASELINE_SHA[BASE_CONDITION] or digest(np) != PINNED_BASELINE_SHA[BASE_NOISE]:
        raise ValueError('baseline files differ from pinned original archive SHA256')
    c,n = json.loads(cp.read_text()),json.loads(np.read_text())
    if c.get('schema') != 'h3-event-audit-v1' or n.get('schema') != 'h3-event-noise-v1':
        raise ValueError('unexpected baseline audit schema')
    return c,n,{'conditioning':digest(cp),'noise':digest(np),'implementation':core_digest()}


def require_zero_gate(root, provenance):
    marker = json.loads((root/(ZERO_ID+'_zero_gate.json')).read_text())
    if (marker.get('passed') is not True or marker.get('provenance') != provenance
            or marker.get('condition_run_id') != ZERO_ID or marker.get('zero_gate') is not True):
        raise ValueError('A0 actual encoding + paired-noise gate missing/stale/failed')
    condition_path = root/(ZERO_ID+'_conditioning.json')
    if marker.get('condition_sha256') != digest(condition_path):
        raise ValueError('A0 accepted conditioning manifest changed after acceptance')
    accepted = json.loads(condition_path.read_text())
    if accepted['semantic_clock']['checks'].get('zero_embedding_and_tokens_bitwise') is not True:
        raise ValueError('A0 zero-equivalence check is not true')
    return marker


class H3SemanticClockReference:
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')  # External zero gate/baseline files must never be bypassed by cache.

    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'clip':('CLIP',),'vae':('VAE',),'ref_video':('IMAGE',),'ref_image':('IMAGE',),
            'prompt':('STRING',{'multiline':True}),
            'width':('INT',{'default':1312}),'height':('INT',{'default':736}),'length':('INT',{'default':141}),
            'audit_dir':('STRING',{'default':str(REMOTE_ROOT/'audit')}),
            'run_id':('STRING',{'default':ZERO_ID}),
            'pixel_phase_frames':('INT',{'default':0,'min':0,'max':6}),
            'label_phase_frames':('INT',{'default':0,'min':0,'max':6})}}
    RETURN_TYPES=('CONDITIONING','LATENT','IMAGE','LATENT')
    RETURN_NAMES=('positive','target_latent','prepared_video','reference_video_latent')
    FUNCTION='encode'
    CATEGORY='research/MiniMax H3 staged semantic clock'

    def encode(self,clip,vae,ref_video,ref_image,prompt,width,height,length,audit_dir,run_id,
               pixel_phase_frames=0,label_phase_frames=0):
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        from comfy.ldm.minimax.model import PackedLayout
        clock_plan(length,pixel_phase_frames,label_phase_frames)
        if (width,height,length) != (1312,736,141):
            raise ValueError('fixed source05 full geometry required')
        root=task_path(audit_dir,mkdir=True); safe_id(run_id)
        baseline,_,provenance=read_baselines()
        zero=pixel_phase_frames == label_phase_frames == 0
        if zero != (run_id == ZERO_ID):
            raise ValueError('A0 has a reserved distinct conditioning identity')
        if not zero:
            require_zero_gate(root,provenance)
        else:
            # A fresh A0 attempt invalidates any earlier acceptance until it passes.
            (root/(ZERO_ID+'_zero_gate.json')).unlink(missing_ok=True)
        store=Store(root); vp=VAEProxy(vae,store)
        cp=ClipProxy(clip,vp,store,pixel_phase_frames,label_phase_frames)
        result=MiniMaxH3ReferenceToVideo.execute(clip=cp,vae=vp,prompt=prompt,
            width=width,height=height,length=length,ref_image_size='match',
            ref_images={'ref_image_0':ref_image},ref_videos={'ref_video_0':ref_video})
        cond,target=result[0],result[1]
        if len(cond)!=1 or cp.tokenize_calls!=1:
            raise ValueError('exactly one native condition/tokenizer call required')
        embedding,meta=cond[0]; refs=meta['minimax_refs']
        video,audio=target['samples'].unbind()
        layout=PackedLayout(embedding.shape[1],*video.shape[2:],audio.shape[-1],refs=refs)
        manifest={'schema':'h3-event-audit-v1','run_id':run_id,'prompt':prompt,
            'input_video':store.tensor(ref_video,save=False),'native_vae_calls':vp.calls,
            'qwen_presentation':cp.presentation,'tokenization_before_vision_expansion':cp.tokens,
            'conditioning_embedding':store.tensor(embedding,save=False),
            'token_tags':store.tensor(meta['minimax_token_tags']),
            'target_latent_shapes':[list(video.shape),list(audio.shape)],
            'packed_layout':{'seq_len':layout.seq_len,'segments':layout.segments,
                             'position_ids':store.tensor(layout.position_ids)},
            'semantic_clock':{'pixel_phase_frames':pixel_phase_frames,'label_phase_frames':label_phase_frames,
                              'provenance':provenance}}
        manifest['semantic_clock']['timestamp_lexical_tokens']=cp.timestamp_lexical_tokens
        text_checks=verify_timestamp_only_text(cp.tokens,baseline['tokenization_before_vision_expansion'],cp.timestamp_lexical_tokens)
        checks=verify_against_baseline(manifest,baseline,layout,pixel_phase_frames,label_phase_frames)
        checks.update(text_checks)
        manifest['semantic_clock']['checks']=checks
        atomic_json(root/(run_id+'_conditioning.json'),manifest)
        return cond,target,vp.video_frames,{'samples':next(r for r in refs if r['kind']=='video')['latent']}


class GuardedNoise(CachedNoise):
    """Revalidate current baseline, condition and zero gate on *every* noise use."""
    def generate_noise(self,input_latent):
        _,expected,provenance=read_baselines()
        condition_id=self.run_id+'_condition'
        if condition_id != ZERO_ID:
            require_zero_gate(self.root,provenance)
        manifest=json.loads((self.root/(condition_id+'_conditioning.json')).read_text())
        if (manifest['semantic_clock']['provenance'] != provenance or
                not manifest['semantic_clock']['checks']['baseline_invariants_passed']):
            raise ValueError('noise use has stale/unaccepted encoded condition')
        noise=super().generate_noise(input_latent)
        leaves=noise.unbind() if noise.is_nested else [noise]
        if [tensor_info(t)[0] for t in leaves] != identity(expected['actual_noise_streams']):
            raise ValueError('generated noise differs from pinned native baseline')
        return noise


class H3SemanticClockNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'noise_seed':('INT',{'default':2026101311}),
            'audit_dir':('STRING',{'default':str(REMOTE_ROOT/'audit')}),'run_id':('STRING',),
            'pair_id':('STRING',{'default':'05_sam_1312x736_2026101311_v3'})}}
    RETURN_TYPES=('NOISE',); FUNCTION='get_noise'; CATEGORY=H3SemanticClockReference.CATEGORY
    def get_noise(self,noise_seed,audit_dir,run_id,pair_id):
        if noise_seed!=2026101311 or pair_id!='05_sam_1312x736_2026101311_v3':
            raise ValueError('frozen seed1 and paired-noise identity required')
        return (GuardedNoise(noise_seed,task_path(audit_dir,mkdir=True),safe_id(run_id),safe_id(pair_id)),)


class H3SemanticClockGate:
    """A0 terminal output node; also a mandatory dependency before B/C/D sampling."""
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'positive':('CONDITIONING',),'target':('LATENT',),'noise':('NOISE',),
            'audit_dir':('STRING',{'default':str(REMOTE_ROOT/'audit')}),'condition_run_id':('STRING',)}}
    RETURN_TYPES=('CONDITIONING','LATENT'); FUNCTION='verify'; OUTPUT_NODE=True
    CATEGORY=H3SemanticClockReference.CATEGORY
    def verify(self,positive,target,noise,audit_dir,condition_run_id):
        root=task_path(audit_dir,mkdir=True);safe_id(condition_run_id)
        if condition_run_id == ZERO_ID:
            (root/(ZERO_ID+'_zero_gate.json')).unlink(missing_ok=True)
        _,baseline_noise,provenance=read_baselines()
        manifest=json.loads((root/(condition_run_id+'_conditioning.json')).read_text())
        clock=manifest['semantic_clock']
        if clock['provenance']!=provenance or not clock['checks']['baseline_invariants_passed']:
            raise ValueError('conditioning acceptance changed or failed')
        if tensor_info(positive[0][0])[0] != identity(manifest['conditioning_embedding']):
            raise ValueError('gate received stale/different condition tensor')
        actual_noise=noise.generate_noise(target)
        leaves=actual_noise.unbind() if actual_noise.is_nested else [actual_noise]
        hashes=[tensor_info(t)[0] for t in leaves]
        if hashes!=identity(baseline_noise['actual_noise_streams']):
            raise ValueError('actual generated paired noise differs from frozen native')
        record={'passed':True,'condition_run_id':condition_run_id,'provenance':provenance,
                'actual_noise_streams':hashes,'condition_sha256':digest(root/(condition_run_id+'_conditioning.json')),
                'zero_gate':condition_run_id==ZERO_ID}
        if condition_run_id==ZERO_ID:
            if not clock['checks']['zero_embedding_and_tokens_bitwise']:
                raise ValueError('A0 actual Qwen output is not native-equivalent')
            atomic_json(root/(ZERO_ID+'_zero_gate.json'),record)
        else:
            require_zero_gate(root,provenance)
        atomic_json(root/(condition_run_id+'_accepted.json'),record)
        return positive,target

NODE_CLASS_MAPPINGS={c.__name__:c for c in (H3SemanticClockReference,H3SemanticClockNoise,H3SemanticClockGate)}
NODE_DISPLAY_NAME_MAPPINGS={k:k for k in NODE_CLASS_MAPPINGS}
