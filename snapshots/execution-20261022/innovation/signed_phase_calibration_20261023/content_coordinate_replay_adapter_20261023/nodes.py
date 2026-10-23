"""Explicit-release single sampler entry; no graph submission or model loading CLI."""
import json
from pathlib import Path
import torch
try:
    from .adapter import ContentCoordinateSampler
    from .identity import file_sha, check_files, check_sources, check_checkpoint_stat, load_live_inputs, exact_tensor, unpack, write_json
except ImportError:
    from adapter import ContentCoordinateSampler
    from identity import file_sha, check_files, check_sources, check_checkpoint_stat, load_live_inputs, exact_tensor, unpack, write_json

HERE = Path(__file__).parent


def finalize_outer(root, samples, raw, shapes):
    gate_path = Path(root) / 'GATE.json'
    gate = json.loads(gate_path.read_text())
    try:
        if gate['status'] != 'forwards_complete' or not gate['outer_normalization_pending']:
            raise ValueError('finite forward gate not ready for outer normalization')
        if not getattr(samples, 'is_nested', False):
            raise ValueError('outer sampler must retain AV normalization')
        video, audio = unpack(raw, shapes)
        sv, sa = samples.unbind()
        exact_tensor(sv.cpu(), video, 'single outer video normalization')
        exact_tensor(sa.cpu(), audio / 4, 'single outer audio normalization')
        gate.update(status='complete', passed=True, outer_normalization_pending=False,
                    outer_video_exact=True, outer_audio_exact=True)
    except BaseException as error:
        gate.update(status='failed', passed=False, error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        write_json(gate_path, gate)


def preflight(release_path, release_sha):
    """Deployment must supply a root-reviewed task-local release; none shipped."""
    if file_sha(release_path) != release_sha:
        raise ValueError('release SHA mismatch')
    r = json.loads(Path(release_path).read_text())
    if (r.get('schema') != 'h3-content-coordinate-root-release-v1'
            or r.get('scope') != 'two_zero_only'
            or r.get('maximum_attempts') != 1 or r.get('cohort') != 'content_coordinate_calibration'):
        raise ValueError('invalid bounded release')
    ready = json.loads((HERE / 'READY.json').read_text())
    if r['ready_sha256'] != file_sha(HERE / 'READY.json') or r['policy_sha256'] != file_sha(HERE / 'POLICY.json'):
        raise ValueError('release/source package mismatch')
    check_files([dict(path=str(HERE / p), sha256=h) for p, h in ready['files_sha256'].items()])
    contract = json.loads((HERE / 'native_contract.json').read_text())
    identity = json.loads((HERE / 'input_identity.json').read_text())
    if r['native_contract_sha256'] != file_sha(HERE / 'native_contract.json'):
        raise ValueError('new live contract mismatch')
    if r['live_inputs'] != json.loads((HERE / 'live_inputs.json').read_text()):
        raise ValueError('only the frozen new native live captures are allowed')
    # Frozen existing full-SHA receipt plus current stat avoids rehashing 20GB.
    check_checkpoint_stat(identity['model_current_stat_matches_full_sha'])
    check_sources(r['core_root'], identity['core_source_shas'])
    check_files(identity['payloads'])
    check_files(r['additional_frozen_runtime_assets'])
    actual_env = dict(torch=str(torch.__version__), cuda=torch.version.cuda)
    if r['environment'] != actual_env:
        raise ValueError('same-environment Torch/CUDA versions differ')
    inputs = load_live_inputs(r['live_inputs'], contract)
    return r, contract, inputs


class H3ContentCoordinateReplay:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': dict(noise=('NOISE',), guider=('GUIDER',), sigmas=('SIGMAS',), latent_image=('LATENT',),
                                 release_file=('STRING', {'default': ''}), release_sha256=('STRING', {'default': ''}),
                                 output_dir=('STRING', {'default': ''}))}
    RETURN_TYPES = ('STRING',)
    FUNCTION = 'run'
    OUTPUT_NODE = True
    CATEGORY = 'research/H3ContentCoordinate'

    @torch.inference_mode()
    def run(self, noise, guider, sigmas, latent_image, release_file, release_sha256, output_dir):
        release, contract, inputs = preflight(release_file, release_sha256)
        if noise.seed != contract['seed'] or latent_image.get('noise_mask') is not None:
            raise ValueError('original seed/no-mask required')
        root = Path(output_dir)
        if not root.is_absolute() or root.exists() or str(root) != release['output_dir']:
            raise ValueError('fresh released task-local output required')
        import comfy.sample, comfy.samplers
        latent = dict(latent_image)
        latent['samples'] = comfy.sample.fix_empty_latent_channels(guider.model_patcher, latent['samples'],
            latent.get('downscale_ratio_spacial'), latent.get('downscale_ratio_temporal'))
        if (not getattr(latent['samples'], 'is_nested', False)
                or [list(t.shape) for t in latent['samples'].unbind()] != contract['target_shapes']):
            raise ValueError('complete original AV target required')
        # Root must inspect the actual zero evidence before any swap release.
        # The current production entry can only execute two zero calls. The
        # four-call orchestration is CPU-tested but has no production route yet.
        fn = ContentCoordinateSampler(inputs, contract, root, allow_swap=False)
        sampler = comfy.samplers.KSAMPLER(fn)
        # Exactly one existing preparation path. Finite sampler never calls its
        # callback and never updates x with Euler, so no trajectory is fabricated.
        samples = guider.sample(noise.generate_noise(latent), latent['samples'], sampler, sigmas,
            denoise_mask=None, callback=None, disable_pbar=True, seed=noise.seed)
        finalize_outer(root, samples, fn.last_raw, contract['target_shapes'])
        return (str(root / 'GATE.json'),)


NODE_CLASS_MAPPINGS = {'H3ContentCoordinateReplay': H3ContentCoordinateReplay}
