#!/usr/bin/env python3
"""Decode one recorded x0 with the existing Comfy H3 video VAE, never a DiT.

No work occurs on import. --validate-only is CPU-only. Real decode requires an
explicit idle GPU UUID and the existing Comfy core, dependencies, VAE and ffmpeg.
"""

import argparse
import gc
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_idle_gpu(uuid):
    # Retained interface for standalone bridge; admission now uses actual free
    # memory and the own-user card cap, while foreign users may coexist.
    return t.standalone_decoder_admission(uuid)


def load_snapshot(path, core):
    import torch
    require = t.require
    r = REQUEST
    require(path.resolve() == Path(r['endpoint_file']).resolve() and t.sha(path) == r['endpoint_file_sha256'], 'Live endpoint file differs')
    payload = torch.load(path, map_location='cpu', weights_only=True)
    require(set(payload) == {'video','audio','metadata'}, 'Live endpoint schema')
    meta=payload['metadata']
    for key in ('physical_index','branch','nfe_index','seed','sigma','sigma_next','condition_sha256','reference_sha256','raw_stream_signatures'):
        require(meta[key] == r[key], 'Live endpoint metadata differs: '+key)
    geometry=t.geometry_for(r['run_id'])
    require(r.get('geometry')==geometry.video_geometry and r.get('observation_domain')==geometry.domain_record,'Live request geometry/domain differs')
    for name,shape in zip(('video','audio'),geometry.stream_shapes):
        v=payload[name]
        require(v.device.type=='cpu' and v.dtype==torch.float32 and tuple(v.shape)==shape and bool(torch.isfinite(v).all()), 'Live tensor contract')
    require([core.tensor_signature(payload[k]) for k in ('video','audio')]==r['normalized_stream_signatures'], 'Live normalized signatures')
    require([core.tensor_signature(payload['video']),core.tensor_signature(payload['audio']*4)]==r['raw_stream_signatures'], 'Live audio/video normalization')
    # Metadata only: exact video/audio objects returned, no tensor transformation.
    payload['metadata']=dict(meta,geometry=geometry.video_geometry,normalization_stage='after_process_latent_out',request_sha256=REQUEST_SHA)
    return payload


def install_fallback_guard(vae_class):
    installed=[]
    def forbidden(*args,**kwargs):
        FALLBACK['calls']+=1
        raise RuntimeError('R19 rejects OOM spatial tiled fallback')
    for name in ('decode_tiled','decode_tiled_','decode_tiled_1d','decode_tiled_3d','_decode_tiled_owned'):
        if hasattr(vae_class,name):
            setattr(vae_class,name,forbidden);installed.append(name)
    if not installed or 'decode_tiled_3d' not in installed:
        raise ValueError('Unable to guard actual 3D fallback entry')
    FALLBACK['installed']=installed


def write_video(images, output, ffmpeg):
    """Fixed 24 fps, no geometry conversion/interpolation; only encode RGB frames."""
    fd, temporary = tempfile.mkstemp(prefix=".x0-decode-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    height, width = images.shape[1:3]
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
               "-framerate", "24", "-i", "pipe:0", "-an", "-c:v", "libx264",
               "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", temporary]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    stream_hash = hashlib.sha256()
    decoded_tensor_hash = hashlib.sha256()
    frame_hashes = []
    try:
        for frame in images:
            # Exact 8-bit conversion used by native VideoFromComponents.save_to.
            # Hash native VAE values a frame at a time to avoid a full-clip copy.
            decoded_tensor_hash.update(frame.contiguous().view(__import__("torch").uint8).numpy().tobytes())
            pixels = (frame * 255).clamp(0, 255).byte().contiguous()
            frame_bytes = pixels.numpy().tobytes()
            stream_hash.update(frame_bytes)
            frame_hashes.append(hashlib.sha256(frame_bytes).hexdigest())
            process.stdin.write(frame_bytes)
        process.stdin.close()
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + error[-2000:])
        if output.exists():
            raise FileExistsError(str(output))
        os.replace(temporary, output)
        return {"preencode_rgb24_sha256": stream_hash.hexdigest(),
                "preencode_rgb24_frame_sha256": frame_hashes,
                "preencode_quantization": "native SaveVideo: (frame * 255).clamp(0, 255).byte(); truncate, no rounding",
                "decoded_tensor_sha256": decoded_tensor_hash.hexdigest(),
                "decoded_tensor_hash_layout": "contiguous FHWC raw dtype bytes, streamed one frame at a time"}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.stderr:
            process.stderr.close()
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_runtime_paths(core, runtime_deps, vae, frozen):
    """Compare actual targets while retaining the bound deployment aliases."""
    resolved = {}
    for key, given in (("comfy", core), ("runtime_deps", runtime_deps), ("vae", vae)):
        actual = Path(given).resolve(strict=True)
        expected = Path(frozen[key]).resolve(strict=True)
        t.require(actual == expected, "Decoder runtime path differs: " + key)
        resolved[key] = str(actual)
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--parent-json", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--core", type=Path)
    parser.add_argument("--runtime-deps", type=Path)
    parser.add_argument("--vae", type=Path)
    parser.add_argument("--expected-vae-sha256")
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    global REQUEST, REQUEST_SHA
    t.install_lifetime_guard(json.loads(args.parent_json))
    REQUEST=t.request(args.request);REQUEST_SHA=t.sha(args.request)
    global ATTEMPT_DIRECTORY
    ATTEMPT_DIRECTORY=args.request.parent.resolve()
    attempt=os.environ.get('H3_DECODER_ATTEMPT_DIRECTORY')
    if attempt is not None:
        import re
        ATTEMPT_DIRECTORY=t.inside(attempt,t.ROOT/'audit/observations')
        t.require(ATTEMPT_DIRECTORY.parent==args.request.parent.resolve() and re.fullmatch(r'decoder_attempt00[1-3]',ATTEMPT_DIRECTORY.name),'Unexpected decoder attempt directory')
    t.require(args.output.resolve()==ATTEMPT_DIRECTORY/'native.mp4','Unexpected output path')
    frozen=t.bindings(external=False)
    resolved_runtime = validate_runtime_paths(args.core, args.runtime_deps, args.vae, frozen)
    t.require(args.gpu_uuid in t.DECODER_UUIDS and args.expected_vae_sha256==frozen['vae_sha256'],'Decoder GPU/model differs')
    profile=t.decoder_memory_profile(bootstrap=ATTEMPT_DIRECTORY.name.startswith('known_endpoint_'))
    t.require(profile['geometry']==REQUEST['geometry'] and profile['vae_sha256']==frozen['vae_sha256'],'Decoder profile geometry/model differs')
    task_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(task_root / "extensions"))
    reader_core = importlib.import_module("H3X0Readout.core")
    payload = load_snapshot(args.snapshot.resolve(), reader_core)
    if args.validate_only:
        import torch
        vae_hash = file_sha256(args.vae)
        t.require(vae_hash == frozen['vae_sha256'], 'VAE checkpoint SHA mismatch')
        t.require(not torch.cuda.is_initialized(), 'CPU validation initialized CUDA')
        print(json.dumps({"valid": True, "metadata": payload["metadata"],
                          "resolved_runtime": resolved_runtime, "vae_sha256": vae_hash,
                          "cuda_initialized": False}, indent=2))
        return 0
    if not all((args.core, args.vae, args.output, args.gpu_uuid)):
        parser.error("decode requires --core, --vae, --gpu-uuid and --output")
    core_path, vae_path, output = args.core.resolve(), args.vae.resolve(), args.output.resolve()
    if not (core_path / "comfy" / "sd.py").is_file() or not vae_path.is_file():
        raise FileNotFoundError("existing Comfy core or VAE is missing")
    if output.suffix.lower() != ".mp4" or output.exists() or output.with_suffix(".json").exists():
        raise ValueError("output must be a new .mp4 path")
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        raise FileNotFoundError("existing ffmpeg executable is required")
    vae_hash = file_sha256(vae_path)
    if args.expected_vae_sha256 and vae_hash != args.expected_vae_sha256:
        raise ValueError("VAE checkpoint SHA mismatch")
    resource_deadline = float(os.environ.get('H3_DECODER_RESOURCE_DEADLINE', time.monotonic()+600))
    admission = t.wait_decoder_admission(REQUEST['parent'],args.gpu_uuid,deadline=resource_deadline,audit_path=ATTEMPT_DIRECTORY/'decoder_admission.jsonl')
    # Comfy chooses its device at import. Scope it to one admitted physical GPU.
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("CUDA initialized before GPU admission")
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_uuid
    if args.runtime_deps:
        if not args.runtime_deps.is_dir():
            raise FileNotFoundError("runtime-deps directory missing")
        sys.path.insert(0, str(args.runtime_deps.resolve()))
    sys.path.insert(0, str(core_path))
    admission = t.wait_decoder_admission(REQUEST['parent'],args.gpu_uuid,deadline=resource_deadline,audit_path=ATTEMPT_DIRECTORY/'decoder_admission.jsonl')
    t.require(t.sha(args.request)==REQUEST_SHA,'request changed during resource wait')
    t.request(args.request)  # revalidate endpoint/data binding immediately before CUDA
    marker = os.environ.get('H3_DECODER_EXECUTION_MARKER')
    if marker is not None:
        marker = t.inside(marker,t.ROOT/'audit/observations')
        t.require(marker==ATTEMPT_DIRECTORY/'decoder_cuda_started.json','execution marker outside current observation')
        own_identity = t.identity(os.getpid())
        t.require(own_identity is not None,'decoder execution identity unavailable')
        t.write_new(marker,{'schema':'h3-child-execution-start-v1','identity':own_identity,'started_monotonic':time.monotonic()})
    # Reuse the frozen runtime's Torch2.5 schema/PyAV adapters, without invoking
    # its server launcher or INT8 DiT row guard. This VAE checkpoint is FP16.
    from compatibility_bootstrap import install, install_video_compat
    install()
    install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram = True
    comfy.cli_args.args.disable_cuda_malloc = True
    comfy.cli_args.args.use_pytorch_cross_attention = True
    import comfy.sd
    import comfy.utils
    import comfy.model_management
    install_fallback_guard(comfy.sd.VAE)

    output.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": "h3-x0-decode-v1", "request_sha256": REQUEST_SHA, "fallback_guard": FALLBACK, "status": "running", "pid": os.getpid(),
              "uid": os.getuid(), "snapshot": str(args.snapshot.resolve()),
              "snapshot_sha256": file_sha256(args.snapshot), "snapshot_metadata": payload["metadata"],
              "vae": str(vae_path), "vae_sha256": vae_hash, "core": str(core_path),
              "gpu_admission": admission, "vae_dtype": "torch.float16", "fps": 24,
              "runtime_flags": {"disable_dynamic_vram": True, "disable_cuda_malloc": True,
                                "use_pytorch_cross_attention": True},
              "processing": "native full-latent VAE.decode; native RGB clamp/truncate-to-uint8; H264 CRF16 yuv420p; no interpolation",
              "comparison_note": "do not require MP4 bitwise equality across encoder libraries; compare normalized tensors/preencode frames",
              "started_unix": time.time()}
    record_path = output.with_suffix(".json")
    reader_core.atomic_write(record_path, record)
    vae = images = state = None
    try:
        if torch.cuda.device_count() != 1:
            raise RuntimeError("expected exactly one visible GPU")
        state, metadata = comfy.utils.load_torch_file(str(vae_path), return_metadata=True)
        vae = comfy.sd.VAE(sd=state, metadata=metadata, dtype=torch.float16)
        vae.throw_exception_if_invalid()
        if (vae.latent_channels != 24 or vae.latent_dim != 3
                or not isinstance(vae.first_stage_model, comfy.ldm.minimax.vae.MiniMaxH3VideoVAE)):
            raise ValueError("provided checkpoint is not H3 video VAE")
        del state
        state = None
        with torch.inference_mode():
            images = vae.decode(payload["video"])
        if images.ndim == 5 and images.shape[0] == 1:
            images = images.flatten(0, 1)
        geometry = payload["metadata"]["geometry"]
        expected = (geometry["frames"], geometry["height"], geometry["width"], 3)
        if tuple(images.shape) != expected or not bool(torch.isfinite(images).all()):
            raise ValueError(f"decoded shape/finite check failed: {tuple(images.shape)} != {expected}")
        images = images.detach().cpu()
        record["decoded_shape"] = list(images.shape)
        record["decoded_dtype"] = str(images.dtype)
        record["decoded_range"] = [float(images.min()), float(images.max())]
        record.update(write_video(images, output, ffmpeg))
        record["output_sha256"] = file_sha256(output)
        record["status"] = "complete"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        images = vae = state = None
        comfy.model_management.unload_all_models()
        gc.collect()
        comfy.model_management.soft_empty_cache()
        record["finished_unix"] = time.time()
        record["process_gpu_memory_reserved_bytes_after_cleanup"] = torch.cuda.memory_reserved()
        record["max_memory_allocated_bytes"] = torch.cuda.max_memory_allocated()
        record["max_memory_reserved_bytes"] = torch.cuda.max_memory_reserved()
        reader_core.atomic_write(record_path, record)
    print(json.dumps({"output": str(output), "record": str(record_path)}, indent=2))
    return 0


from observer_import import t
REQUEST = None
REQUEST_SHA = None
ATTEMPT_DIRECTORY = None
FALLBACK = {"calls": 0, "installed": []}

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as error:
        torch_module=sys.modules.get('torch')
        oom_type=getattr(getattr(torch_module,'cuda',None),'OutOfMemoryError',None)
        chain=t.typed_cuda_oom(error,oom_type)
        if chain is not None and REQUEST is not None and ATTEMPT_DIRECTORY is not None:
            t.write_new(ATTEMPT_DIRECTORY/'decoder_oom.json',{'schema':'h3-typed-cuda-oom-v4','typed_cuda_oom':True,'exception_chain':chain,'identity':t.identity(os.getpid()),'request_sha256':REQUEST_SHA,**{key:REQUEST[key] for key in ('endpoint_file_sha256','seed','geometry')}})
            raise SystemExit(t.CUDA_OOM_EXIT) from error
        raise
