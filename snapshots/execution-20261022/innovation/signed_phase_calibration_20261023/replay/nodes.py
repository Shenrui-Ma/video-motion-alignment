"""Opt-in finite historical diagnostic node; no VAE, sampler loop, or video output."""
import json
from pathlib import Path
import torch
try:
    from .one_forward import HistoricalOneForward,verify_pair
    from .reconstruct import file_sha,tensor_info
    from .noise import H3HistoricalNoise
except ImportError:
    from one_forward import HistoricalOneForward,verify_pair
    from reconstruct import file_sha,tensor_info
    from noise import H3HistoricalNoise

class H3HistoricalReplayGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'noise':('NOISE',),'guider':('GUIDER',),'sigmas':('SIGMAS',),'latent_image':('LATENT',),
            **{k:('STRING',{'default':''}) for k in ('state_file','state_sha256','historical_x0_file','historical_x0_sha256','provenance_file','provenance_sha256','output_dir','case','method')},
            'valid_frames':('INT',{'default':105,'min':1})}}
    RETURN_TYPES=('STRING',)
    FUNCTION='run'
    OUTPUT_NODE=True
    CATEGORY='research/H3PassiveReplay'

    @torch.inference_mode()
    def run(self,noise,guider,sigmas,latent_image,state_file,state_sha256,historical_x0_file,historical_x0_sha256,provenance_file,provenance_sha256,output_dir,case,method,valid_frames):
        import comfy.sample,comfy.samplers,comfy.model_management
        root=Path(output_dir)
        if not root.is_absolute():raise ValueError('absolute task-local output required')
        root.mkdir(parents=True,exist_ok=False)
        if file_sha(provenance_file)!=provenance_sha256:raise ValueError('frozen provenance identity mismatch')
        provenance=json.loads(Path(provenance_file).read_text())
        # Prepared by resource-owner only after historical video/graph/x0/cache links checked.
        required={'case','method','display_video_sha256','historical_graph_sha256','capture_manifest_sha256','model_checkpoint_sha256','source_identity_verified','assets_verified'}
        if not required<=provenance.keys() or provenance['source_identity_verified'] is not True or provenance['assets_verified'] is not True:raise ValueError('incomplete exact historical provenance')
        if (provenance['case'],provenance['method'])!=(case,method):raise ValueError('case/method provenance mismatch')
        if case not in ('short_0358','long_0059') or valid_frames!={'short_0358':105,'long_0059':144}[case]:raise ValueError('case/valid frames differ from frozen calibration')
        if method not in ('native','global_weak'):raise ValueError('only frozen controls may be calibrated')
        state=torch.load(state_file,map_location='cpu',weights_only=True)
        if state['manifest_sha256']!=provenance['capture_manifest_sha256']:raise ValueError('state does not belong to display control')
        if latent_image.get('noise_mask') is not None:raise ValueError('original controls must have no denoise mask')
        # Use the actual SamplerCustomAdvanced preparation, excluding preview/x0 callback.
        latent=dict(latent_image)
        latent['samples']=comfy.sample.fix_empty_latent_channels(guider.model_patcher,latent['samples'],latent.get('downscale_ratio_spacial'),latent.get('downscale_ratio_temporal'))
        if not getattr(latent['samples'],'is_nested',False):raise ValueError('complete AV nested target required')
        if [list(t.shape) for t in latent['samples'].unbind()]!=state['shapes']:raise ValueError('prepared AV target shapes differ')
        modes={}; gate={'schema':'h3-passive-replay-release-v1','case':case,'method':method,'passed':False,'provenance_sha256':provenance_sha256,'provenance':provenance}
        try:
            for capture_on,label in ((False,'off'),(True,'on')):
                fn=HistoricalOneForward(state_file,state_sha256,historical_x0_file,historical_x0_sha256,root/label,capture_on=capture_on,valid_frames=valid_frames,expected_method=method,case=case)
                sampler=comfy.samplers.KSAMPLER(fn)
                # Keep original noise, BasicGuider condition preparation, CFG/model-predict
                # wrappers, sample_sigmas, AV noise and final normalization paths.
                samples=guider.sample(noise.generate_noise(latent),latent['samples'],sampler,sigmas,
                                      denoise_mask=None,callback=None,disable_pbar=True,seed=noise.seed)
                if not getattr(samples,'is_nested',False):raise ValueError('guider returned non-AV output')
                returned={k:t.detach().to('cpu',copy=True) for k,t in zip(('video','audio'),samples.unbind())}
                if not all(torch.equal(returned[k],fn.normalized[k]) for k in returned):raise ValueError('actual CFG final normalization differs from raw-x0 comparison copy')
                modes[label]=fn
            off,on=modes['off'],modes['on'];gate.update(verify_pair(off.normalized,on.normalized,off.old))
            gate['schema']='h3-passive-replay-release-v1'
            raw_equal=torch.equal(off.raw_result,on.raw_result)
            gate['raw_full_AV_hook_exact_equal']=raw_equal;gate['passed'] &= raw_equal
            gate.update(step_zero_based=off.step,layer_zero_based=25,
                        state_sha256=state_sha256,historical_x0_sha256=historical_x0_sha256,
                        raw_denoised_off=tensor_info(off.raw_result),raw_denoised_on=tensor_info(on.raw_result),
                        denoised_off_file_sha256=file_sha(root/'off/denoised.pt'),denoised_on_file_sha256=file_sha(root/'on/denoised.pt'),
                        qk_file=str(root/'on/qk.pt'),qk_file_sha256=file_sha(root/'on/qk.pt'),qk_sha256=file_sha(root/'on/qk.pt'),input_identity=off.input_identity,
                        display_video_sha256=provenance['display_video_sha256'],original_video_sha256=provenance['display_video_sha256'])
            (root/'REPLAY_GATE.json').write_text(json.dumps(gate,indent=2,allow_nan=False)+'\n')
            if not gate['passed']:raise RuntimeError('frozen same-state historical replay gates failed; no calibration release')
            return (str(root/'REPLAY_GATE.json'),)
        except BaseException as error:
            gate.update(passed=False,error=type(error).__name__+': '+str(error))
            (root/'REPLAY_GATE.json').write_text(json.dumps(gate,indent=2,allow_nan=False)+'\n')
            raise

NODE_CLASS_MAPPINGS={'H3HistoricalReplayGate':H3HistoricalReplayGate,'H3HistoricalNoise':H3HistoricalNoise}
NODE_DISPLAY_NAME_MAPPINGS={'H3HistoricalReplayGate':'H3 finite historical-state passive calibration'}
