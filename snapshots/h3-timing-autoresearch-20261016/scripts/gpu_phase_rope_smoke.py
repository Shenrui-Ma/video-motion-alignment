"""Bounded tensor-only check on one explicitly idle GPU; never loads a DiT."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


def coordinate_rope(query, positions, frequency):
    """Independent full 96-dimensional split-half coordinate recomputation."""
    import torch
    per_axis = positions.to(query).unsqueeze(-1) * frequency.to(query)
    angles = torch.cat(tuple(per_axis.unbind(1)), dim=-1)
    c, s = angles.cos()[None, None], angles.sin()[None, None]
    first, second = query[..., :48], query[..., 48:96]
    result = query.clone()
    result[..., :48], result[..., 48:96] = first*c-second*s, first*s+second*c
    return result


def coordinate_checks(frequency, TemporalRotation, device, try_kitchen=True):
    import torch
    generator = torch.Generator(device=device).manual_seed(159)
    raw = torch.randn(1, 4, 8, 128, generator=generator, device=device, dtype=torch.float64)
    positions = torch.tensor([[0,0,0], [5/3,1,2], [47*5/3,3,4], [65*5/3,5,6],
                              [6960,1,1], [7196,2,3], [7274+1/3,3,2], [7304+1/3,4,4]],
                             device=device, dtype=torch.float64)
    base = coordinate_rope(raw, positions, frequency.double())
    rows = []
    for delta in (-12.0, 12.0, 0.25):
        shifted = positions.clone()
        shifted[:, 0] += delta * 5/3
        direct = coordinate_rope(raw, shifted, frequency.double())
        composed = TemporalRotation(frequency.double(), delta)(base)
        error = composed-direct
        torch.testing.assert_close(composed, direct, atol=2e-10, rtol=2e-10)
        assert torch.equal(composed[...,16:48], base[...,16:48])
        assert torch.equal(composed[...,64:], base[...,64:])
        rows.append({'delta_frames': delta, 'max_abs_fp64': float(error.abs().max()),
                     'rms_fp64': float(error.square().mean().sqrt())})
    result = {'independent_full_coordinate_recomputation': rows,
              'includes_large_packed_time_coordinates': True,
              'kitchen': {'status': 'not_requested', 'claim': 'mathematical comparison only'}}
    if not try_kitchen:
        return result
    try:
        from compatibility_bootstrap import install
        install()
        import comfy_kitchen as kitchen
        # Current .9 Core disables this compiled CUDA backend for torch cu121.
        # Explicitly call the installed eager partial-RoPE implementation instead
        # of asking the registry to select an unsupported CUDA13 kernel.
        kitchen.disable_backend('cuda')
        from comfy_kitchen.backends.eager import rope as eager_rope
    except ImportError as error:
        raise RuntimeError('Installed kitchen eager comparison unavailable; no native check claimed') from error
    function = getattr(eager_rope, 'rms_rope_split_half_', None)
    if not callable(function):
        raise RuntimeError('Installed eager partial split-half API is unavailable')
    def table(pos, dtype):
        # Current H3 rope_freqs and rope_rotation_table use FP32 coordinates.
        axes = pos.float().unsqueeze(-1) * frequency.to(device=device, dtype=torch.float32).view(1,1,-1)
        angles = torch.cat(tuple(axes.unbind(1)), -1)
        c, s = angles.cos(), angles.sin()
        return torch.stack((c,-s,s,c), -1).reshape(1,8,1,48,2,2).to(dtype)
    rows = []
    for dtype in (torch.float32, torch.bfloat16):
        original = raw.to(dtype).transpose(1,2).contiguous()
        weights = torch.ones(128, device=device, dtype=dtype)
        base_q, _ = function(original.clone(), original.clone(), table(positions,dtype),
                             weights, weights, epsilon=1e-5, rot_dim=96)
        base_q = base_q.transpose(1,2)
        for delta in (-12.0,12.0,0.25):
            shifted = positions.clone()
            shifted[:,0] += delta * 5/3
            direct_q, _ = function(original.clone(), original.clone(), table(shifted,dtype),
                                   weights, weights, epsilon=1e-5, rot_dim=96)
            composed = TemporalRotation(frequency,delta)(base_q)
            error = composed.float()-direct_q.transpose(1,2).float()
            maximum, rms = float(error.abs().max()), float(error.square().mean().sqrt())
            # Extra rotation adds BF16 rounding; large FP32 coordinates add
            # argument rounding for fractional frame offsets. Do not demand bitwise.
            tolerance = (0.005,0.0006) if dtype==torch.float32 else (0.0625,0.012)
            assert maximum <= tolerance[0] and rms <= tolerance[1], (dtype,delta,maximum,rms)
            assert torch.equal(composed[...,16:48], base_q[...,16:48])
            assert torch.equal(composed[...,64:], base_q[...,64:])
            rows.append({'dtype': str(dtype), 'delta_frames': delta, 'max_abs': maximum,
                         'rms': rms, 'predeclared_max_rms_tolerance': list(tolerance)})
    result['kitchen'] = {'status':'passed', 'api':'comfy_kitchen.backends.eager.rope.rms_rope_split_half_',
                         'module':str(Path(eager_rope.__file__).resolve()), 'rot_dim':96,
                         'module_sha256':hashlib.sha256(Path(eager_rope.__file__).read_bytes()).hexdigest(),
                         'backend_selection':'explicit installed eager implementation; CUDA backend disabled locally',
                         'service_relation':'same partial split-half eager implementation; does not test CUDA13 or Triton fused full-RoPE kernel',
                         'scope':'actual installed eager API, tiny tensors, unit RMS weights, no model forward', 'rows':rows}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cpu-self-test', action='store_true')
    parser.add_argument('--skip-kitchen', action='store_true', help='Explicit mathematical-only coordinate comparison')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.cpu_self_test:
        os.environ['CUDA_VISIBLE_DEVICES']=''
        import torch
        sys.path.insert(0,str(root/'extensions_staged'))
        from H3PhaseRoPE.core import TemporalRotation
        result=coordinate_checks(torch.linspace(0.0001,1,16),TemporalRotation,'cpu',False)
        assert not torch.cuda.is_initialized()
        print(json.dumps({'success':True,'cpu_only':True,'frequency_is_toy_not_checkpoint':True,
                          'cuda_initialized':False,'checks':result},indent=2))
        return
    if not all((args.gpu_uuid,args.checkpoint,args.output)):
        parser.error('GPU check requires --gpu-uuid, --checkpoint and --output')
    if args.output.exists():
        raise FileExistsError(args.output)
    if not args.gpu_uuid.startswith('GPU-'):
        raise ValueError('explicit GPU UUID required')
    query = subprocess.check_output(['nvidia-smi', '-i', args.gpu_uuid,
        '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True).strip()
    uuid, memory, util = [x.strip() for x in query.split(',')]
    processes = subprocess.check_output(['nvidia-smi', '-i', args.gpu_uuid,
        '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip()
    if uuid != args.gpu_uuid or int(memory) > 64 or int(util) or processes:
        raise RuntimeError('selected GPU is not idle')
    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu_uuid
    os.environ['OMP_NUM_THREADS'] = '4'
    import torch
    from safetensors import safe_open
    sys.path.insert(0, str(root/'extensions_staged'))
    sys.path.insert(0, str(root/'extensions'))
    from H3PhaseRoPE.core import TemporalRotation, phase_attention
    from H3PhaseRoPE.audited_flash import flash_attention_lse
    from H3TemporalRouter.core import flash_attention_lse as frozen_flash
    assert torch.cuda.device_count() == 1
    with safe_open(args.checkpoint, framework='pt', device='cpu') as handle:
        keys = [k for k in handle.keys() if k.endswith('rope.inv_freq')]
        if len(keys) != 1:
            raise ValueError(f'expected one model RoPE frequency buffer: {keys}')
        frequency = handle.get_tensor(keys[0])
    record = {'pid': os.getpid(), 'uid': os.getuid(), 'gpu_uuid': uuid,
              'admission': query, 'kind': 'tensor-only; one checkpoint frequency buffer, no model forward',
              'started_unix': time.time(), 'checkpoint_frequency_key': keys[0],
              'frequency_sha256': hashlib.sha256(frequency.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest(),
              'cases': [], 'torch_version': str(torch.__version__),
              'frequency_values': frequency.double().tolist(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    torch.backends.cuda.matmul.allow_tf32=False
    generator = torch.Generator(device='cuda').manual_seed(7413)
    packed = torch.randn(1,256,3,56,128,generator=generator,device='cuda',dtype=torch.bfloat16)
    q, k, v = [x.transpose(1,2) for x in packed.unbind(2)]
    record['initial_qkv_strides']=[list(x.stride()) for x in (q,k,v)]
    original = [x.clone() for x in (q, k, v)]
    plan = {'query_interval_half_open': [200, 224], 'reference_video_segment': [12, 160]}
    native, _ = frozen_flash(q, k, v)
    native_flat = native.transpose(1, 2).reshape(1, 256, 56*128)
    cases=[(False,0.,1.),(False,12.,0.),(False,-12.,1.),(False,12.,1.),(False,0.25,1.),
           (True,0.,1.),(True,12.,0.),(True,-12.,1.),(True,12.,1.),(True,0.25,1.)]
    high_mass_ready=False
    for high_mass,delta,alpha in cases:
        if high_mass and not high_mass_ready:
            q,k,v=[x.clone() for x in original]
            signal_q=q[:,:,200:201].clone()
            q[:,:,200:224]=signal_q
            perturbation=torch.randn(1,56,148,128,generator=generator,device='cuda',dtype=torch.float32)*0.25
            k[:,:,12:160]=(signal_q.float()*3+perturbation).bfloat16()
            original=[x.clone() for x in (q,k,v)]
            native,_=frozen_flash(q,k,v)
            native_flat=native.transpose(1,2).reshape(1,256,56*128)
            high_mass_ready=True
        rotation = TemporalRotation(frequency, delta)
        stats,calls = [],[]
        def counted_flash(*values):
            calls.append(1)
            return flash_attention_lse(*values)
        result = phase_attention(q, k, v, 56, plan, rotation=rotation, alpha=alpha,
                                 attention=counted_flash, diagnostics=stats)
        assert all(torch.equal(a, b) for a, b in zip(original, (q,k,v)))
        assert torch.equal(result[:, :200], native_flat[:, :200])
        assert torch.equal(result[:, 224:], native_flat[:, 224:])
        assert bool(torch.isfinite(result).all())
        row = {'delta_frames': delta, 'alpha': alpha, 'high_reference_mass': high_mass,
               'inputs_unchanged': True, 'untouched_queries_bitwise_equal': True,
               'flash_calls':len(calls),'q_stride':list(q.stride())}
        if delta == 0 or alpha == 0:
            assert torch.equal(result, native_flat)
            assert len(calls)==1 and not stats
            row['zero_or_alpha0_exact_frozen_native'] = True
        else:
            # Match the actual BF16-quantized rotated Q before constructing a
            # higher precision reference probability distribution.
            rotated = rotation(q[:, :, 200:224])
            logits = q.float() @ k.float().transpose(-1,-2) / (128**.5)
            probabilities = logits.softmax(-1)
            mass = probabilities[:, :, 200:224, 12:160].sum(-1, keepdim=True)
            if high_mass:
                assert float(mass.min())>0.999, float(mass.min())
            shifted = (rotated.float() @ k[:, :, 12:160].float().transpose(-1,-2) / (128**.5)).softmax(-1)
            probabilities[:, :, 200:224, 12:160] = mass*shifted
            dense = (probabilities @ v.float()).transpose(1,2).reshape(1,256,56*128)
            delta_value = result.float()[:, 200:224]-dense[:, 200:224]
            rms = float(delta_value.square().mean().sqrt())
            max_abs = float(delta_value.abs().max())
            # Fixed before execution; tolerates BF16 branch outputs and correction.
            assert max_abs < 0.025 and rms < 0.003, (max_abs, rms)
            assert len(calls)==3
            assert torch.equal(rotated[...,16:48], q[:,:,200:224,16:48])
            assert torch.equal(rotated[...,64:], q[:,:,200:224,64:])
            row.update(max_abs_vs_dense_fp32=max_abs,rms_vs_dense_fp32=rms,
                       predeclared_max_rms_tolerance=[0.025,0.003],
                       reference_mass_min=float(mass.min()),reference_mass_max=float(mass.max()),
                       sampled_stats=stats[0].cpu().tolist(), spatial_and_other_channels_unchanged=True)
        record['cases'].append(row)
    # Preserve completed attention evidence even if the separate kitchen test fails.
    record['attention_checks_passed']=True
    record['success']=False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    try:
        record['coordinate_checks']=coordinate_checks(frequency,TemporalRotation,'cuda',not args.skip_kitchen)
    except BaseException as error:
        record.update(error=repr(error),finished_unix=time.time(),coordinate_check_failed=True)
        args.output.write_text(json.dumps(record,indent=2)+'\n')
        raise
    record['actual_installed_kitchen_verified']=record['coordinate_checks']['kitchen']['status']=='passed'
    torch.cuda.synchronize()
    record.update(success=True,finished_unix=time.time(),peak_allocated_bytes=torch.cuda.max_memory_allocated())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
