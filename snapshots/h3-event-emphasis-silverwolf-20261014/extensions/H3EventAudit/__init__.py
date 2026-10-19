"""Isolated H3 pilot instrumentation; no model/core/attention monkey-patching.

The reference node delegates preprocessing to the installed native node. A
proxy records its actual VAE inputs and tokenizer presentation. Default 2 FPS,
phase 0 passes native tokenization arguments through unchanged.
"""

import hashlib
import json
import os
from pathlib import Path
import re

import torch


def safe_id(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) or value in {".", ".."}:
        raise ValueError("audit identifiers must be simple filename components")
    return value


def audit_root(value):
    root = Path(value)
    if not root.is_absolute() or "event_emphasis_silverwolf_20261014" not in root.parts:
        raise ValueError("audit_dir must be under the task's event_emphasis_silverwolf_20261014 directory")
    root.mkdir(parents=True, exist_ok=True)
    return root


def atomic_json(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, path)


def tensor_info(tensor):
    cpu = tensor.detach().to("cpu").contiguous()
    digest = hashlib.sha256(cpu.view(torch.uint8).numpy().data).hexdigest()
    return {"shape": list(cpu.shape), "dtype": str(cpu.dtype), "sha256": digest}, cpu


class Store:
    def __init__(self, root):
        self.root = root
        self.blobs = root / "tensor_blobs"
        self.blobs.mkdir(exist_ok=True)

    def tensor(self, tensor, save=True):
        info, cpu = tensor_info(tensor)
        if save:
            # Shape/dtype supplement the raw-byte hash in filenames.
            identity = json.dumps(info, sort_keys=True).encode()
            filename = hashlib.sha256(identity).hexdigest() + ".pt"
            path = self.blobs / filename
            if not path.exists():
                tmp = path.with_name(path.name + ".tmp")
                torch.save(cpu, tmp)
                os.replace(tmp, path)
            info["tensor_file"] = str(path.relative_to(self.root))
        return info


def sampling_plan(frame_count, semantic_fps, phase):
    if semantic_fps not in (1, 2, 3, 4, 6, 8, 12, 24):
        raise ValueError("semantic_fps must divide the actual 24 FPS source")
    stride = 24 // semantic_fps
    if phase < 0 or phase >= stride or phase >= frame_count:
        raise ValueError("phase must be a valid source-frame offset smaller than stride")
    indices = list(range(phase, frame_count, stride))
    timestamps = [index / 24.0 for index in indices]
    padded_indices = indices + indices[-1:] if len(indices) % 2 else indices
    padded_times = timestamps + timestamps[-1:] if len(timestamps) % 2 else timestamps
    blocks = []
    for index in range(0, len(padded_indices), 2):
        timestamp = sum(padded_times[index:index + 2]) / 2
        blocks.append({"source_frames": padded_indices[index:index + 2],
                       "timestamp_seconds": timestamp,
                       "rendered_timestamp": "<%.1f seconds>" % timestamp})
    return {"source_fps": 24, "semantic_fps": semantic_fps, "phase_frames": phase,
            "sample_indices": indices, "sample_timestamps_seconds": timestamps,
            "temporal_blocks": blocks}


class VAEProxy:
    def __init__(self, native, store):
        self.native = native
        self.store = store
        self.calls = []
        self.video_frames = None

    def __getattr__(self, name):
        return getattr(self.native, name)

    def encode(self, frames, *args, **kwargs):
        if frames.shape[0] > 1:
            self.video_frames = frames
        prepared = self.store.tensor(frames)
        latent = self.native.encode(frames, *args, **kwargs)
        self.calls.append({"prepared_frames": prepared,
                           "latent": self.store.tensor(latent)})
        return latent


def token_ledger(value, store):
    if isinstance(value, torch.Tensor):
        return {"tensor": store.tensor(value, save=False)}
    if isinstance(value, dict):
        return {str(k): token_ledger(v, store) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [token_ledger(v, store) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("unrecognized tokenization object: " + type(value).__name__)


class ClipProxy:
    def __init__(self, native, vae, store, semantic_fps, phase):
        self.native, self.vae, self.store = native, vae, store
        self.semantic_fps, self.phase = semantic_fps, phase
        self.presentation = []
        self.tokens = None

    def __getattr__(self, name):
        return getattr(self.native, name)

    def tokenize(self, prompt, **kwargs):
        items = kwargs["minimax_ref_items"]
        updated = []
        for item in items:
            if item["type"] != "video":
                updated.append(item)
                self.presentation.append(token_ledger(item, self.store))
                continue
            frames = self.vae.video_frames
            if frames is None:
                raise ValueError("missing native prepared video frames")
            plan = sampling_plan(len(frames), self.semantic_fps, self.phase)
            if self.semantic_fps == 2 and self.phase == 0:
                # Test exact equivalence; never silently replace default inputs.
                expected = frames[plan["sample_indices"]]
                if not torch.equal(item["data"], expected) or item["timestamps"] != plan["sample_timestamps_seconds"]:
                    raise ValueError("native Qwen default sampling changed; re-audit required")
                modified = item
            else:
                modified = dict(item, data=frames[plan["sample_indices"]],
                                timestamps=plan["sample_timestamps_seconds"])
            updated.append(modified)
            self.presentation.append({"type": "video", "sampling": plan,
                                      "actual_sampled_frames": self.store.tensor(modified["data"])})
        if self.semantic_fps != 2 or self.phase != 0:
            kwargs = dict(kwargs, minimax_ref_items=updated)
        tokens = self.native.tokenize(prompt, **kwargs)
        self.tokens = token_ledger(tokens, self.store)
        return tokens


class H3EventAuditReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP",), "vae": ("VAE",), "ref_video": ("IMAGE",),
            "prompt": ("STRING", {"multiline": True}),
            "width": ("INT", {"default": 1312, "min": 32, "step": 32}),
            "height": ("INT", {"default": 736, "min": 32, "step": 32}),
            "length": ("INT", {"default": 107, "min": 5}),
            "audit_dir": ("STRING", {"default": "/data5/researcher/h3_runs/event_emphasis_silverwolf_20261014/audit"}),
            "run_id": ("STRING", {"default": "case_A_seed1"}),
            "semantic_fps": ("INT", {"default": 2, "min": 1, "max": 24}),
            "phase_frames": ("INT", {"default": 0, "min": 0, "max": 23}),
        }, "optional": {"ref_image": ("IMAGE",)}}

    RETURN_TYPES = ("CONDITIONING", "LATENT", "IMAGE", "LATENT")
    RETURN_NAMES = ("positive", "target_latent", "prepared_video", "reference_video_latent")
    FUNCTION = "encode"
    CATEGORY = "research/MiniMax H3"

    def encode(self, clip, vae, ref_video, prompt, width, height, length,
               audit_dir, run_id, semantic_fps=2, phase_frames=0, ref_image=None):
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        from comfy.ldm.minimax.model import PackedLayout

        root = audit_root(audit_dir)
        safe_id(run_id)
        store = Store(root)
        vp = VAEProxy(vae, store)
        cp = ClipProxy(clip, vp, store, semantic_fps, phase_frames)
        result = MiniMaxH3ReferenceToVideo.execute(
            clip=cp, vae=vp, prompt=prompt, width=width, height=height, length=length,
            ref_image_size="match", ref_images=None if ref_image is None else {"ref_image_0": ref_image},
            ref_videos={"ref_video_0": ref_video})
        cond, target = result[0], result[1]
        if len(cond) != 1:
            raise ValueError("pilot only supports one unscheduled conditioning entry")
        embedding, meta = cond[0]
        refs = meta["minimax_refs"]
        video, audio = target["samples"].unbind()
        layout = PackedLayout(embedding.shape[1], *video.shape[2:], audio.shape[-1], refs=refs)
        video_ref = next(ref for ref in refs if ref["kind"] == "video")
        manifest = {
            "schema": "h3-event-audit-v1", "run_id": run_id, "prompt": prompt,
            "input_video": store.tensor(ref_video, save=False),
            "native_vae_calls": vp.calls, "qwen_presentation": cp.presentation,
            "tokenization_before_vision_expansion": cp.tokens,
            "conditioning_embedding": store.tensor(embedding, save=False),
            "token_tags": store.tensor(meta["minimax_token_tags"]),
            "target_latent_shapes": [list(video.shape), list(audio.shape)],
            "packed_layout": {"seq_len": layout.seq_len, "segments": layout.segments,
                              "position_ids": store.tensor(layout.position_ids)},
            "notes": ["Default 2 FPS phase 0 delegates native arguments unchanged.",
                      "Dense VAE input is unchanged by semantic FPS/phase settings.",
                      "Phase/FPS may change token count and RoPE layout; compare manifests.",
                      "Native reference augmentation is deterministic: visual 0.999, per-reference CPU RNG restarted at sampler seed; audio uses seed+1.",
                      "Only silent video and optional image are supported by this pilot node."]}
        atomic_json(root / (run_id + "_conditioning.json"), manifest)
        return cond, target, vp.video_frames, {"samples": video_ref["latent"]}


class CachedNoise:
    def __init__(self, seed, root, run_id, pair_id):
        self.seed = seed
        self.root, self.run_id, self.pair_id = root, run_id, pair_id

    def generate_noise(self, input_latent):
        import comfy.sample
        from comfy.nested_tensor import NestedTensor

        samples = input_latent["samples"]
        nested = bool(samples.is_nested)
        leaves = samples.unbind() if nested else [samples]
        batch_index = input_latent.get("batch_index")
        if batch_index is not None and hasattr(batch_index, "tolist"):
            batch_index = batch_index.tolist()
        signature = {"seed": self.seed, "nested": nested,
                     "shapes": [list(t.shape) for t in leaves],
                     "dtypes": [str(t.dtype) for t in leaves], "batch_index": batch_index}
        cache = self.root / (self.pair_id + "_noise.pt")
        if cache.exists():
            saved = torch.load(cache, map_location="cpu", weights_only=True)
            if saved["signature"] != signature:
                raise ValueError("paired noise geometry/seed/dtype mismatch; use a new pair_id")
            tensors = saved["tensors"]
            for tensor, expected in zip(tensors, saved["hashes"]):
                if tensor_info(tensor)[0] != expected:
                    raise ValueError("paired noise cache hash mismatch")
        else:
            noise = comfy.sample.prepare_noise(samples, self.seed, input_latent.get("batch_index"))
            tensors = noise.unbind() if nested else [noise]
            hashes = [tensor_info(t)[0] for t in tensors]
            saved = {"signature": signature, "tensors": tensors, "hashes": hashes}
            tmp = cache.with_name(cache.name + ".tmp")
            torch.save(saved, tmp)
            os.replace(tmp, cache)
        if len(tensors) != len(leaves):
            raise ValueError("invalid number of cached noise streams")
        manifest = {"schema": "h3-event-noise-v1", "run_id": self.run_id,
                    "pair_id": self.pair_id, "signature": signature,
                    "actual_noise_streams": [tensor_info(t)[0] for t in tensors],
                    "cache_file": str(cache)}
        atomic_json(self.root / (self.run_id + "_noise.json"), manifest)
        copied = [t.clone() for t in tensors]
        return NestedTensor(copied) if nested else copied[0]


class H3EventAuditNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "noise_seed": ("INT", {"default": 12345, "min": 0, "max": 0xffffffffffffffff}),
            "audit_dir": ("STRING", {"default": "/data5/researcher/h3_runs/event_emphasis_silverwolf_20261014/audit"}),
            "run_id": ("STRING", {"default": "case_A_seed1"}),
            "pair_id": ("STRING", {"default": "case_seed1"}),
        }}

    RETURN_TYPES = ("NOISE",)
    FUNCTION = "get_noise"
    CATEGORY = "research/MiniMax H3"

    def get_noise(self, noise_seed, audit_dir, run_id, pair_id):
        return (CachedNoise(noise_seed, audit_root(audit_dir), safe_id(run_id), safe_id(pair_id)),)


NODE_CLASS_MAPPINGS = {"H3EventAuditReference": H3EventAuditReference,
                       "H3EventAuditNoise": H3EventAuditNoise}
NODE_DISPLAY_NAME_MAPPINGS = {key: key for key in NODE_CLASS_MAPPINGS}
