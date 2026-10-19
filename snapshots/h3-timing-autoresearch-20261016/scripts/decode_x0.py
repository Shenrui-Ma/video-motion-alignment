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
    if not uuid or not uuid.startswith("GPU-") or any(c.isspace() for c in uuid):
        raise ValueError("an explicit full GPU UUID is required")
    text = subprocess.check_output([
        "nvidia-smi", "--id=" + uuid,
        "--query-gpu=uuid,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
    rows = [row.strip().split(",") for row in text.splitlines() if row.strip()]
    if len(rows) != 1 or rows[0][0].strip() != uuid:
        raise RuntimeError("GPU UUID did not resolve exactly")
    if int(rows[0][1]) > 64 or int(rows[0][2]) != 0:
        raise RuntimeError("GPU is not idle; refusing offline decode")
    processes = subprocess.check_output([
        "nvidia-smi", "--id=" + uuid, "--query-compute-apps=pid",
        "--format=csv,noheader,nounits"], text=True).strip()
    if processes:
        raise RuntimeError("GPU has a compute process; refusing offline decode")
    return {"uuid": uuid, "memory_used_mib": int(rows[0][1]), "utilization_percent": int(rows[0][2])}


def load_snapshot(path, core):
    import torch

    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or set(payload) != {"video", "audio", "metadata"}:
        raise ValueError("unexpected snapshot keys")
    meta = payload["metadata"]
    if not isinstance(meta, dict) or meta.get("schema") != core.SCHEMA:
        raise ValueError("unsupported x0 schema")
    if meta.get("normalization_stage") != "after_process_latent_out":
        raise ValueError("snapshot is not VAE-ready")
    if meta.get("step_zero_based") not in core.CAPTURE_STEPS or meta.get("total_steps") != 20:
        raise ValueError("unexpected capture step")
    if meta.get("snapshot_kind") not in ("x0_estimate", "sampler_final"):
        raise ValueError("unexpected snapshot kind")
    if meta["snapshot_kind"] == "sampler_final" and meta["step_zero_based"] != 19:
        raise ValueError("unexpected final sampler step")
    if meta.get("endpoint_sanity") != (meta["step_zero_based"] == 19):
        raise ValueError("endpoint sanity marker mismatch")
    geometry = meta["geometry"]
    if geometry.get("fps") != 24:
        raise ValueError("expected unresampled 24 fps")
    config = core.CaptureConfig(meta["run_id"], str(Path(path).resolve().parent),
                                geometry["width"], geometry["height"], geometry["frames"])
    for name, shape in zip(("video", "audio"), config.shapes):
        value = payload[name]
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != shape or value.dtype != torch.float32:
            raise ValueError(f"invalid {name} tensor")
        if not bool(torch.isfinite(value).all()) or core.tensor_signature(value) != meta[name]:
            raise ValueError(f"nonfinite or hash-mismatched {name}")
    manifest_path = Path(path).parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "complete" or manifest.get("schema") != core.SCHEMA:
        raise ValueError("capture run is incomplete")
    if manifest.get("run_id") != meta["run_id"] or manifest.get("geometry") != geometry:
        raise ValueError("manifest identity/geometry mismatch")
    entries = list(manifest["captures"]) + [manifest.get("final_sampler_result", {})]
    captures = [c for c in entries if c.get("file") == Path(path).name]
    if len(captures) != 1 or any(captures[0].get(k) != v for k, v in meta.items()):
        raise ValueError("snapshot metadata mismatch with completed manifest")
    return payload


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--core", type=Path)
    parser.add_argument("--runtime-deps", type=Path)
    parser.add_argument("--vae", type=Path)
    parser.add_argument("--expected-vae-sha256")
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    task_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(task_root / "extensions_staged"))
    reader_core = importlib.import_module("H3X0Readout.core")
    payload = load_snapshot(args.snapshot.resolve(), reader_core)
    if args.validate_only:
        print(json.dumps({"valid": True, "metadata": payload["metadata"]}, indent=2))
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
    admission = assert_idle_gpu(args.gpu_uuid)
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
    assert_idle_gpu(args.gpu_uuid)  # check again immediately before CUDA/Comfy initialization
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

    output.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": "h3-x0-decode-v1", "status": "running", "pid": os.getpid(),
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
        reader_core.atomic_write(record_path, record)
    print(json.dumps({"output": str(output), "record": str(record_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
