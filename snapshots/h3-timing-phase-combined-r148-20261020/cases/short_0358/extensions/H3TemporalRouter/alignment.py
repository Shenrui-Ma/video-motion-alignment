"""Registered single-video media-clock alignment; no learned parameters."""

import hashlib
import json
from pathlib import Path
import time


def tensor_sha(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def aligned_positions(layout, metadata):
    """Canonical single-video aligned layout, preserving the original object.

    This reproduces not advancing the media cursor after the one video reference.
    It is intentionally restricted to equal reference/target grids and no other
    references or keyframes. Content tokens and their ordering are untouched.
    """
    import torch

    refs = metadata.get("refs", [])
    if len(refs) != 1 or refs[0]["kind"] != "video" or refs[0]["ref_audio_t"] != 0:
        raise ValueError("alignment requires exactly one silent video reference")
    ref = refs[0]
    text, vt, vh, vw, at = layout.signature
    if (text, vt, vh, vw) != (metadata["text_len"], ref["latent_t"], ref["latent_h"], ref["latent_w"]):
        raise ValueError("reference/target grid or text signature mismatch")
    if tuple(metadata.get("context_shape", ()))[:2] != (1, text):
        raise ValueError("alignment requires a single conditioning batch")
    if vh % 2 or vw % 2 or min(vt, vh, vw, at) <= 0:
        raise ValueError("unexpected target geometry")
    fr = (vh // 2) * (vw // 2)
    if ref["frame_rows"] != fr or tuple(ref["latent_shape"]) != (1, 24, vt, vh, vw):
        raise ValueError("unexpected reference geometry")
    expected = [
        (0, text, "text"),
        (text, text + vt * fr, "ref_img"),
        (text + vt * fr, text + vt * fr + at * 2, "audio"),
        (text + vt * fr + at * 2, text + 2 * vt * fr + at * 2, "video"),
    ]
    if list(layout.segments) != expected:
        raise ValueError("unexpected segments, reference audio, keyframes or mixed modalities")
    pos = layout.position_ids
    if pos.device.type != "cpu" or pos.dtype != torch.float64 or tuple(pos.shape) != (layout.seq_len, 3):
        raise ValueError("expected original CPU float64 PackedLayout positions")
    if layout.seq_len != expected[-1][1] or not torch.isfinite(pos).all():
        raise ValueError("invalid packed sequence")
    ra, rb, _ = expected[1]
    aa, ab, _ = expected[2]
    va, vb, _ = expected[3]
    if not torch.equal(pos[ra:rb, 1:], pos[va:vb, 1:]):
        raise ValueError("reference and target spatial coordinates differ")
    ref_t = pos[ra:rb, 0]
    target_t = pos[va:vb, 0]
    ref_origin, target_origin = float(ref_t[0]), float(target_t[0])
    delta = target_origin - ref_origin
    spans = torch.tensor([(1, 4, 4, 4, 4)[i % 5] * (5.0 / 3.0) for i in range(vt)], dtype=torch.float64)
    offsets = torch.cat((torch.zeros(1, dtype=torch.float64), spans[:-1].cumsum(0)))
    expected_ref = (ref_origin + offsets).repeat_interleave(fr)
    expected_target = (target_origin + offsets).repeat_interleave(fr)
    if not torch.equal(ref_t, expected_ref) or not torch.equal(target_t, expected_target):
        raise ValueError("video coordinates no longer follow the registered H3 time grid")
    if ref_origin != float(text) or abs(delta - float(sum(spans.tolist()))) > 1e-8:
        raise ValueError("unexpected original media cursor")
    audio_offsets = torch.arange(at, dtype=torch.float64).repeat(2)
    if not torch.equal(pos[aa:ab, 0], target_origin + audio_offsets):
        raise ValueError("target audio/video origins differ")

    result = pos.clone()
    # Exact reconstruction avoids round-off from subtracting two large origins.
    result[va:vb, 0] = ref_t
    result[aa:ab, 0] = ref_origin + audio_offsets
    if not torch.equal(result[:aa], pos[:aa]) or not torch.equal(result[:, 1:], pos[:, 1:]):
        raise AssertionError("non-target or spatial coordinates changed")
    displacement = result[aa:, 0] - pos[aa:, 0]
    residual = float((displacement + delta).abs().max())
    if residual > 1e-8:
        raise AssertionError("target media streams did not share a common clock shift")
    audit = {
        "signature": list(layout.signature), "segments": [list(s) for s in expected],
        "reference_origin": ref_origin, "original_target_origin": target_origin,
        "aligned_target_origin": ref_origin, "target_time_displacement": -delta,
        "canonical_reconstruction_max_translation_roundoff": residual,
        "original_position_sha256": tensor_sha(pos), "aligned_position_sha256": tensor_sha(result),
        "changed_rows": ab - aa + vb - va, "changed_coordinate": "time",
        "reference_text_unchanged": True, "spatial_unchanged": True,
        "target_video_matches_reference_all_coordinates": bool(torch.equal(result[va:vb], result[ra:rb])),
        "target_audio_video_common_origin": True,
    }
    return result, audit


class AlignmentState:
    """One fixed rotation table shared by all blocks and denoising steps."""

    def __init__(self, metadata, diffusion, rope_rotation_table, run_id, audit_dir, enabled=True):
        self.metadata = metadata
        self.diffusion = diffusion
        self.rotation_fn = rope_rotation_table
        self.run_id, self.enabled = run_id, enabled
        self.path = Path(audit_dir) / (run_id + "_alignment.json")
        self.layout = self.original = self.positions = self.table = self.table_key = None
        self.next_block = self.forward_index = 0
        self.audit = {
            "schema": "h3-r129-aligned-media-clock-v1", "run_id": run_id,
            "enabled": enabled, "configuration": "single-video aligned media-clock; temporal router native",
            "expected_sampling_steps": 20, "expected_blocks": 50,
            "completed_calls": 0, "calls_by_block": [0] * 50, "calls_by_forward": [],
            "rotation_table_builds": 0, "created_unix": time.time(), "status": "prepared",
            "first_six_prediction_equality_required": False,
        }

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.audit, indent=2) + "\n")
        temporary.replace(self.path)

    def rotation_for(self, args, block_index):
        import torch

        if block_index != self.next_block or not 0 <= self.forward_index < 20:
            raise ValueError("unexpected aligned block order or forward count")
        layout = args["layout"]
        source_table = args["rope_freqs"]
        if self.layout is None:
            if block_index != 0:
                raise ValueError("first alignment call must be block zero")
            self.positions, details = aligned_positions(layout, self.metadata)
            self.layout, self.original = layout, layout.position_ids.clone()
            self.audit["layout"] = details
        if layout is not self.layout:
            raise ValueError("PackedLayout identity changed during the run")
        if block_index == 0:
            if not torch.equal(layout.position_ids, self.original):
                raise ValueError("original PackedLayout was modified")
            self.audit["calls_by_forward"].append(0)
        if not self.enabled:
            return source_table
        key = (source_table.device, source_table.dtype, tuple(source_table.shape))
        if source_table.shape[:3] != (1, layout.seq_len, 1) or source_table.shape[-3:] != (48, 2, 2):
            raise ValueError("unexpected H3 rotation table shape")
        if self.table is None:
            angles = self.diffusion.rope_freqs(self.positions, source_table.device)
            self.table = self.rotation_fn(angles, source_table.dtype)
            if self.table.shape != source_table.shape or not torch.isfinite(self.table).all():
                raise ValueError("invalid aligned rotation table")
            self.table_key = key
            self.audit["rotation_table_builds"] += 1
            self.audit["table_dtype"] = str(source_table.dtype)
            self.audit["table_device"] = str(source_table.device)
            self.audit["table_shape"] = list(self.table.shape)
            probe_rows = sorted({0, self.layout.segments[1][0], self.layout.segments[2][0], self.layout.segments[3][0], self.layout.seq_len - 1})
            self.audit["table_probe_rows"] = probe_rows
            self.audit["table_probe_float32_sha256"] = tensor_sha(self.table[0, probe_rows].float())
        elif key != self.table_key:
            raise ValueError("rotation table device, dtype or geometry changed")
        return self.table

    def completed(self, block_index):
        self.audit["completed_calls"] += 1
        self.audit["calls_by_block"][block_index] += 1
        self.audit["calls_by_forward"][self.forward_index] += 1
        self.next_block = (block_index + 1) % 50
        if self.next_block == 0:
            self.forward_index += 1
            self.audit["status"] = "complete" if self.forward_index == 20 else "sampling"
            self.audit["completed_sampling_steps"] = self.forward_index
            self.write()


class AlignedBlockPatch:
    """Change only the RoPE table, then use the existing Native attention path."""

    def __init__(self, alignment, native_patch, block_index):
        self.alignment, self.native_patch, self.block_index = alignment, native_patch, block_index

    def __call__(self, args, extra_args):
        state = self.alignment
        try:
            local_args = dict(args)
            local_args["rope_freqs"] = state.rotation_for(args, self.block_index)
            result = self.native_patch(local_args, extra_args)
            state.completed(self.block_index)
            return result
        except Exception as error:
            state.audit.update(status="failed", error=repr(error))
            state.write()
            raise
