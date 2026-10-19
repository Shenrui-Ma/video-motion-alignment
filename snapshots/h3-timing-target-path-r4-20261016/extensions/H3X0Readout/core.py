"""Passive, fail-closed H3 Euler20 x0 capture; no Comfy imports at module load."""

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

import torch

CAPTURE_STEPS = (5, 6, 7, 8, 9, 10, 15, 19)
SCHEMA = "h3-x0-readout-v1"


def tensor_signature(tensor):
    value = tensor.detach().to(device="cpu").contiguous()
    return {"shape": list(value.shape), "dtype": str(value.dtype),
            "bytes": value.numel() * value.element_size(),
            "sha256": hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}


def atomic_write(path, payload, *, tensor=False):
    """Replace only a task-owned manifest or newly reserved run's snapshot."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb" if tensor else "w") as handle:
            if tensor:
                torch.save(payload, handle)
            else:
                json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class CaptureConfig:
    run_id: str
    output_dir: str
    width: int = 1312
    height: int = 736
    length: int = 141

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", self.run_id):
            raise ValueError("run_id must be a safe, nonempty single path component")
        if not Path(self.output_dir).is_absolute():
            raise ValueError("output_dir must be absolute")
        if any(type(v) is not int for v in (self.width, self.height, self.length)):
            raise ValueError("geometry must use integers")
        if self.width < 32 or self.height < 32 or self.width % 32 or self.height % 32:
            raise ValueError("target dimensions must be positive multiples of 32")
        if self.length < 5 or self.length % 17 != 5:
            raise ValueError("length must already be on the 17k+5 frame grid")

    @property
    def shapes(self):
        latent_t = ((self.length - 5) // 17) * 5 + 2
        return ((1, 24, latent_t, self.height // 16, self.width // 16),
                (1, 32, 2, round(self.length / 24 * 40)))


def split_streams(value, shapes, unpack):
    """Reject extra packed data: Comfy unpack_latents alone silently ignores it."""
    if getattr(value, "is_nested", False):
        leaves = list(value.unbind())
    else:
        expected = (1, 1, sum(math.prod(shape[1:]) for shape in shapes))
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != expected:
            raise ValueError(f"packed latent shape mismatch: expected {expected}")
        leaves = list(unpack(value, shapes))
    if len(leaves) != 2:
        raise ValueError("exactly video and audio streams are required")
    for label, leaf, shape in zip(("video", "audio"), leaves, shapes):
        if not isinstance(leaf, torch.Tensor) or tuple(leaf.shape) != tuple(shape):
            raise ValueError(f"{label} target shape mismatch: expected {tuple(shape)}")
        if leaf.dtype != torch.float32:
            raise ValueError(f"{label} x0 must be float32 for this verified Euler20 path")
    return leaves


class PassiveRecorder:
    def __init__(self, config, *, unpack=None, nested_factory=None):
        self.config = config
        self.unpack = unpack
        self.nested_factory = nested_factory

    def __call__(self, executor, model_wrap, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        if self.unpack is None:
            from comfy.utils import unpack_latents
            from comfy.nested_tensor import NestedTensor
            unpack, nested_factory = unpack_latents, NestedTensor
        else:
            unpack, nested_factory = self.unpack, self.nested_factory
        model = model_wrap.inner_model
        shapes = tuple(tuple(s) for s in model.latent_shapes)
        if shapes != self.config.shapes:
            raise ValueError(f"model latent_shapes {shapes} != configured {self.config.shapes}")
        sampler = getattr(executor, "class_obj", None)
        if getattr(getattr(sampler, "sampler_function", None), "__name__", None) != "sample_euler":
            raise ValueError("only the audited sample_euler sampler is supported")
        if getattr(sampler, "extra_options", {}).get("s_churn", 0) != 0:
            raise ValueError("Euler churn is unsupported")
        grid = sigmas.detach().to(device="cpu", dtype=torch.float64)
        if grid.ndim != 1 or len(grid) != 21 or not torch.isfinite(grid).all():
            raise ValueError("expected 21 finite sigmas for Euler20")
        if grid[-1].item() != 0 or not torch.all(grid[:-1] > grid[1:]):
            raise ValueError("sigmas must strictly decrease to zero")
        audio_scale = float(model.audio_scale())
        if not math.isfinite(audio_scale) or audio_scale <= 0:
            raise ValueError("invalid H3 audio_scale")
        latent_scale = float(model.latent_format.scale_factor)
        if latent_scale != 1.0:
            raise ValueError("this recorder requires the audited H3 video scale_factor=1")
        seed = extra_args.get("seed")
        if seed is not None and type(seed) is not int:
            raise ValueError("seed metadata must be an integer or None")
        parent = Path(self.config.output_dir).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        run_dir = parent / self.config.run_id
        run_dir.mkdir()  # exclusive reservation; never overwrite another run
        manifest = {
            "schema": SCHEMA, "run_id": self.config.run_id, "status": "running",
            "capture_steps_zero_based": list(CAPTURE_STEPS), "expected_callback_count": 20,
            "geometry": {"width": self.config.width, "height": self.config.height,
                         "frames": self.config.length, "fps": 24},
            "target_latent_shapes": [list(s) for s in shapes], "sigmas_video": grid.tolist(),
            "sampler": "sample_euler", "seed": seed, "audio_scale": audio_scale,
            "video_latent_scale_factor": latent_scale, "torch_version": str(torch.__version__),
            "normalization_stage": "after_process_latent_out",
            "normalization": "video unchanged; audio divided by audio_scale; VAE mean/std left for VAE.decode",
            "snapshot_semantics": "current-sigma denoised estimate before Euler x update",
            "noise": tensor_signature(noise), "captures": [], "callback_count": 0,
            "created_unix": time.time(),
        }
        manifest_path = run_dir / "manifest.json"
        atomic_write(manifest_path, manifest)
        seen = []

        def record(step, x0, x, total_steps):
            if type(step) is not int or total_steps != 20 or step != len(seen) or step >= 20:
                raise ValueError("unexpected, duplicate, skipped, or out-of-order sampler callback")
            seen.append(step)
            manifest["callback_count"] = len(seen)
            if step in CAPTURE_STEPS:
                started = time.perf_counter()
                leaves = split_streams(x0, shapes, unpack)
                raw = [leaf.detach().to(device="cpu", copy=True).contiguous() for leaf in leaves]
                if not all(bool(torch.isfinite(leaf).all()) for leaf in raw):
                    raise ValueError("nonfinite x0")
                # Normalize CPU copies while the model's current AV schedule is still available.
                # Originals, original callback arguments, and sampler state are never reassigned.
                with torch.no_grad():
                    ready = list(model.process_latent_out(nested_factory(raw)).unbind())
                if len(ready) != 2 or any(tuple(t.shape) != s for t, s in zip(ready, shapes)):
                    raise ValueError("process_latent_out changed stream geometry")
                if any(t.device.type != "cpu" or t.dtype != torch.float32 for t in ready):
                    raise ValueError("process_latent_out must preserve CPU float32 copies")
                if not torch.equal(ready[0], raw[0]) or not torch.equal(ready[1], raw[1] * (1 / audio_scale)):
                    raise ValueError("unexpected H3 latent normalization")
                if not all(bool(torch.isfinite(t).all()) for t in ready):
                    raise ValueError("nonfinite normalized x0")
                sigma_v = float(grid[step])
                sigma_a = sigma_v / (audio_scale + (1 - audio_scale) * sigma_v)
                metadata = {"schema": SCHEMA, "run_id": self.config.run_id,
                            "snapshot_kind": "x0_estimate",
                            "step_zero_based": step, "model_call_one_based": step + 1,
                            "total_steps": 20, "endpoint_sanity": step == 19,
                            "sigma_video": sigma_v, "sigma_audio": sigma_a,
                            "sigma_next_video": float(grid[step + 1]),
                            "normalization_stage": manifest["normalization_stage"],
                            "audio_scale": audio_scale, "video_latent_scale_factor": latent_scale,
                            "geometry": manifest["geometry"], "seed": seed,
                            "video": tensor_signature(ready[0]), "audio": tensor_signature(ready[1])}
                path = run_dir / f"x0_step{step:03d}.pt"
                atomic_write(path, {"video": ready[0], "audio": ready[1], "metadata": metadata}, tensor=True)
                manifest["captures"].append({"file": path.name, **metadata,
                                             "capture_seconds": time.perf_counter() - started})
                atomic_write(manifest_path, manifest)
            if callback is not None:
                return callback(step, x0, x, total_steps)

        try:
            result = executor(model_wrap, sigmas, extra_args, record, noise,
                              latent_image, denoise_mask, disable_pbar)
            if seen != list(range(20)):
                raise ValueError("sampler ended without all 20 callbacks")
            if [c["step_zero_based"] for c in manifest["captures"]] != list(CAPTURE_STEPS):
                raise ValueError("incomplete x0 capture")
            # KSAMPLER has returned, but CFGGuider has not yet process_latent_out.
            # Save its true endpoint separately: Euler arithmetic can round slightly
            # differently from step19 x0, so measure rather than demand bitwise equality.
            final_leaves = split_streams(result, shapes, unpack)
            final_cpu = [leaf.detach().to(device="cpu", copy=True).contiguous() for leaf in final_leaves]
            with torch.no_grad():
                final_ready = list(model.process_latent_out(nested_factory(final_cpu)).unbind())
            if len(final_ready) != 2 or any(
                    tuple(t.shape) != shape or t.device.type != "cpu" or t.dtype != torch.float32
                    or not bool(torch.isfinite(t).all()) for t, shape in zip(final_ready, shapes)):
                raise ValueError("invalid normalized final sampler result")
            if not torch.equal(final_ready[0], final_cpu[0]) or not torch.equal(final_ready[1], final_cpu[1] * (1 / audio_scale)):
                raise ValueError("unexpected final sampler normalization")
            final_metadata = {k: v for k, v in manifest["captures"][-1].items()
                              if k not in ("file", "capture_seconds")}
            final_metadata.update(snapshot_kind="sampler_final", sigma_video=0.0, sigma_audio=0.0,
                                  video=tensor_signature(final_ready[0]), audio=tensor_signature(final_ready[1]))
            final_path = run_dir / "sampler_final.pt"
            atomic_write(final_path, {"video": final_ready[0], "audio": final_ready[1],
                                     "metadata": final_metadata}, tensor=True)
            last = torch.load(run_dir / "x0_step019.pt", map_location="cpu", weights_only=True)
            differences = {}
            for name, value in zip(("video", "audio"), final_ready):
                delta = value - last[name]
                differences[name] = {"max_abs": float(delta.abs().max()),
                                     "mean_abs": float(delta.abs().mean()),
                                     "rms": float(delta.square().mean().sqrt())}
            manifest["final_sampler_result"] = {"file": final_path.name, **final_metadata}
            manifest["endpoint_comparison"] = {
                "reference": "x0_step019.pt", "measured": "sampler_final.pt",
                "differences": differences,
                "interpretation": "Euler final arithmetic may round differently; no exact-equality requirement"}
            manifest["status"] = "complete"
            return result
        except BaseException as error:
            manifest["status"] = "failed"
            manifest["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            manifest["finished_unix"] = time.time()
            atomic_write(manifest_path, manifest)
