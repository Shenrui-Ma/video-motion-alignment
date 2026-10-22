"""Passive, bounded H3 Q/K motion descriptors. No model/attention calls.

Read RMSNorm+RoPE Q/K at block25 during the ordinary Euler forward. Match
adjacent frames within each video independently; no cross-video identity match.
DiTFlow/MOFT are related feature-motion prior art; this is an observer diagnostic.
"""
from pathlib import Path
import json
import math
import time

import torch
import torch.nn.functional as F

SPANS = (1, 4, 4, 4, 4)
COLUMNS = ["dx_patches", "dy_patches", "magnitude_patches", "reciprocal_support",
           "mean_cosine_top2_gap", "nonzero_motion_fraction"]


def selected_heads(count, maximum=4):
    if type(count) is not int or count < 1:
        raise ValueError("invalid head count")
    n = min(count, maximum)
    return [0] if n == 1 else [round(i * (count - 1) / (n - 1)) for i in range(n)]


def physical_bins(count, valid_frames, fps):
    if type(count) is not int or count < 2 or type(valid_frames) is not int or valid_frames < 1 or fps <= 0:
        raise ValueError("invalid physical video geometry")
    result, cursor = [], 0
    for i in range(count):
        width = SPANS[i % 5]
        result.append({"bin": i, "frame_span": [cursor, cursor + width - 1],
                       "center_frame": cursor + (width - 1) / 2,
                       "center_seconds": (cursor + (width - 1) / 2) / fps,
                       "fully_valid": cursor + width <= valid_frames})
        cursor += width
    if valid_frames > cursor:
        raise ValueError("valid_frames exceeds H3 positional-bin coverage")
    return result


def inverse_time_rope_copy(x, time_coordinate, inv_freq):
    """Undo only split-half temporal pairs; all spatial/non-RoPE dims retained."""
    if x.shape[-1] != 128 or tuple(inv_freq.shape) != (16,):
        raise ValueError("requires verified H3 128D head / 96D partial split-half RoPE")
    y = x.float().clone()
    angles = inv_freq.to(device=x.device, dtype=torch.float32) * float(time_coordinate)
    c, s = angles.cos(), angles.sin()
    a, b = y[..., :16].clone(), y[..., 48:64].clone()
    y[..., :16] = a * c + b * s
    y[..., 48:64] = -a * s + b * c
    return y


def geometry(rows, cols, device, stride=4, radius=2, tiles=4):
    if min(rows, cols) < 3 or stride < 1 or radius < 1:
        raise ValueError("invalid patch-grid geometry")
    yy, xx = torch.meshgrid(torch.arange(0, rows, stride, device=device),
                            torch.arange(0, cols, stride, device=device), indexing="ij")
    xy = torch.stack((xx.flatten(), yy.flatten()), -1)
    dy, dx = torch.meshgrid(torch.arange(-radius, radius+1, device=device),
                            torch.arange(-radius, radius+1, device=device), indexing="ij")
    offsets = torch.stack((dx.flatten(), dy.flatten()), -1)
    cand_xy = xy[:, None] + offsets[None]
    good = (cand_xy[..., 0] >= 0) & (cand_xy[..., 0] < cols) & (cand_xy[..., 1] >= 0) & (cand_xy[..., 1] < rows)
    candidates = (cand_xy[..., 1].clamp(0, rows-1) * cols + cand_xy[..., 0].clamp(0, cols-1)).long()
    tile_index = (xy[:, 1] * tiles // rows) * tiles + xy[:, 0] * tiles // cols
    return dict(rows=rows, cols=cols, anchors=xy[:, 1] * cols + xy[:, 0], xy=xy,
                offsets=offsets, candidates=candidates, candidate_valid=good,
                tile_index=tile_index, tiles=tiles)


def adjacent_match(source_q, next_k, grid, tie_epsilon=1e-6):
    """[selected_heads, full_frame_patches,128] -> [16,6] small descriptors.

    Reverse search transposes the SAME Q(t)/K(t+1) similarity relation. It does
    not pretend Q(t+1)/K(t) are interchangeable. Candidate radius is in the full
    patch grid; only source anchors use stride4. No full patch/sequence matrix.
    """
    qnorm, knorm = source_q.float().norm(dim=-1), next_k.float().norm(dim=-1)
    q = F.normalize(source_q.float(), dim=-1, eps=1e-12)
    k = F.normalize(next_k.float(), dim=-1, eps=1e-12)
    a, cand, good = grid["anchors"], grid["candidates"], grid["candidate_valid"]
    score = torch.einsum("hpd,hpcd->hpc", q[:, a], k[:, cand]).mean(0)
    usable = good & (qnorm[:, a].min(0).values[:, None] > 1e-12) & (knorm[:, cand].min(0).values > 1e-12)
    score = score.masked_fill(~usable | ~torch.isfinite(score), -float("inf"))
    top = score.topk(2, dim=-1)
    best = cand.gather(1, top.indices[:, :1]).squeeze(1)
    gap = top.values[:, 0] - top.values[:, 1]
    best_xy = torch.stack((best % grid["cols"], best // grid["cols"]), -1)
    reverse_xy = best_xy[:, None] + grid["offsets"][None]
    rg = (reverse_xy[..., 0] >= 0) & (reverse_xy[..., 0] < grid["cols"]) & (reverse_xy[..., 1] >= 0) & (reverse_xy[..., 1] < grid["rows"])
    reverse = (reverse_xy[..., 1].clamp(0, grid["rows"]-1) * grid["cols"] + reverse_xy[..., 0].clamp(0, grid["cols"]-1)).long()
    back_score = torch.einsum("hpd,hpcd->hpc", k[:, best], q[:, reverse]).mean(0)
    rg = rg & (qnorm[:, reverse].min(0).values > 1e-12) & (knorm[:, best].min(0).values[:, None] > 1e-12)
    back_score = back_score.masked_fill(~rg | ~torch.isfinite(back_score), -float("inf"))
    bt = back_score.topk(2, dim=-1)
    back_best = reverse.gather(1, bt.indices[:, :1]).squeeze(1)
    back_gap = bt.values[:, 0] - bt.values[:, 1]
    valid = (back_best == a) & (gap > tie_epsilon) & (back_gap > tie_epsilon) & torch.isfinite(gap) & torch.isfinite(back_gap)
    disp = (best_xy - grid["xy"]).float()
    mag = disp.norm(dim=-1)
    confidence = torch.minimum(gap, back_gap)
    ntiles = grid["tiles"] ** 2
    tile = grid["tile_index"]
    counts = torch.zeros(ntiles, device=q.device).scatter_add_(0, tile, torch.ones_like(mag))
    supported = torch.zeros_like(counts).scatter_add_(0, tile, valid.float())
    values = torch.stack((disp[:,0], disp[:,1], mag,
                          torch.nan_to_num(confidence), (mag > 0).float()), -1)
    sums = torch.zeros((ntiles,5), device=q.device).index_add_(0, tile, values * valid[:, None])
    means = sums / supported.clamp_min(1)[:,None]
    return torch.stack((means[:,0], means[:,1], means[:,2], supported / counts.clamp_min(1),
                        means[:,3], means[:,4]), -1)


class QKMotionProbe:
    """Single-run passive recorder, never used to select interventions.

    Caller passes true Euler index plus pass kind explicitly. The fixed R146
    route has 20 forwards for20 Euler steps, making its index equivalent; an
    automatic extra-Forward run must use transaction physical_index instead.
    """
    def __init__(self, output_dir, *, inv_freq, valid_frames, fps=24, max_bytes=100000):
        if not isinstance(inv_freq, torch.Tensor) or inv_freq.shape != (16,) or not torch.isfinite(inv_freq).all():
            raise ValueError("pass actual diffusion.rope.inv_freq checkpoint buffer")
        self.inv_freq = inv_freq.detach().float().cpu().clone()
        self.output_dir = Path(output_dir)
        self.valid_frames, self.fps, self.max_bytes = valid_frames, fps, max_bytes
        self.seen, self.cache = set(), None

    def _prepare(self, q, k, plan, positions):
        if q.ndim != 4 or q.shape != k.shape or q.shape[0] != 1 or q.shape[-1] != 128:
            raise ValueError("expected H3 Q/K [1,H,S,128]")
        if q.device != k.device or q.dtype != k.dtype or q.shape[2] != plan["seq_len"]:
            raise ValueError("Q/K device/dtype/sequence differs")
        text, bins, height, width, audio = plan["signature"]
        rows, cols = height // 2, width // 2
        if height % 2 or width % 2 or rows * cols != plan["frame_rows"]:
            raise ValueError("invalid H3 2x2 patchification geometry")
        if positions.device.type != "cpu" or tuple(positions.shape) != (q.shape[2],3):
            raise ValueError("pass actual CPU PackedLayout.position_ids")
        key = (tuple(q.shape), str(q.device), str(q.dtype), tuple(plan["reference_video_segment"]), tuple(plan["target_video_segment"]), tuple(plan["signature"]), plan["frame_rows"])
        if self.cache is not None:
            if self.cache["key"] != key:
                raise ValueError("single-run probe geometry/layout changed")
            if not torch.equal(positions, self.cache["position_snapshot"]):
                raise ValueError("PackedLayout coordinates changed")
            return self.cache
        bins_info = physical_bins(bins, self.valid_frames, self.fps)
        usable_pairs = [i for i in range(bins-1) if bins_info[i]["fully_valid"] and bins_info[i+1]["fully_valid"]]
        if not usable_pairs:
            raise ValueError("at least two fully valid H3 temporal bins required")
        starts = torch.tensor([row["frame_span"][0] for row in bins_info], dtype=torch.float64) * (5.0/3.0)
        times, spans = {}, {}
        for stream, field in (("reference","reference_video_segment"),("target","target_video_segment")):
            a,b = plan[field]
            if b-a != bins * rows * cols:
                raise ValueError("reference and target must have equal complete patch grids")
            time_grid = positions[a:b,0].reshape(bins, rows*cols).double()
            expected = time_grid[0,0] + starts[:,None]
            if not torch.allclose(time_grid, expected.expand_as(time_grid), rtol=0, atol=1e-8):
                raise ValueError("actual H3 time positions disagree with physical-bin map")
            times[stream], spans[stream] = time_grid[:,0].tolist(), (a,b)
        self.cache = dict(key=key, position_snapshot=positions.detach().clone(),
                          bins=bins_info, pairs=usable_pairs, times=times, spans=spans,
                          rows=rows, cols=cols, heads=selected_heads(q.shape[1]),
                          grid=geometry(rows,cols,q.device), device_inv_freq=self.inv_freq.to(q.device))
        return self.cache

    @torch.no_grad()
    def observe(self, q, k, plan, positions, *, physical_step, pass_kind, block_index):
        if block_index != 25 or pass_kind != "ordinary":
            return None
        if type(physical_step) is not int or physical_step < 0:
            raise ValueError("explicit nonnegative Euler step required")
        if physical_step in self.seen:
            raise ValueError("duplicate ordinary observation for Euler step")
        started = time.perf_counter()
        cuda = q.device.type == "cuda"
        events = (torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)) if cuda else None
        if events: events[0].record(torch.cuda.current_stream(q.device))
        c = self._prepare(q,k,plan,positions)
        h = torch.tensor(c["heads"], device=q.device)
        descriptors = []
        frame_rows = c["rows"] * c["cols"]
        for variant in ("native", "inverse_time_only"):
            for stream in ("reference","target"):
                base,_ = c["spans"][stream]
                frames = []
                for t in c["pairs"]:
                    a,b = base + t*frame_rows, base+(t+1)*frame_rows
                    qs = q[0, :, a:a+frame_rows].index_select(0,h)
                    ks = k[0, :, b:b+frame_rows].index_select(0,h)
                    if variant == "inverse_time_only":
                        qs = inverse_time_rope_copy(qs,c["times"][stream][t],c["device_inv_freq"])
                        ks = inverse_time_rope_copy(ks,c["times"][stream][t+1],c["device_inv_freq"])
                    frames.append(adjacent_match(qs,ks,c["grid"]))
                descriptors.append(torch.stack(frames))
        if events: events[1].record(torch.cuda.current_stream(q.device))
        data = torch.stack(descriptors).cpu().tolist()
        result = {"schema":"h3-passive-qk-motion-r147-v1", "physical_euler_step":physical_step,
                  "pass_kind":pass_kind, "block_index":25, "head_indices":c["heads"],
                  "patch_grid":[c["rows"],c["cols"]], "stride":4, "radius":2,
                  "columns":COLUMNS, "tile_grid":[4,4], "bins":c["bins"],
                  "transition_start_bins":c["pairs"], "rope_times":c["times"],
                  "actual_inv_freq":self.inv_freq.tolist(), "descriptors":{},
                  "intervention_decision":None,
                  "tensor_bounds":{"full_sequence_matrix":False,"maximum_local_feature_elements":len(c["heads"])*len(c["grid"]["anchors"])*25*128},
                  "timing":{"compute_and_copy_wall_seconds":time.perf_counter()-started,
                            "cuda_stream_elapsed_ms":events[0].elapsed_time(events[1]) if events else None}}
        for name, values in zip(("native_reference","native_target","inverse_time_only_reference","inverse_time_only_target"),data):
            rounded = [[[round(v,4) for v in tile] for tile in frame] for frame in values]
            status = ["MOTION" if any(tile[3] > 0 and tile[2] > 1e-6 for tile in frame) else "UNKNOWN" for frame in values]
            result["descriptors"][name] = {"values":rounded,"transition_status":status}
        payload = json.dumps(result,separators=(",",":"),allow_nan=False).encode()
        if len(payload) > self.max_bytes:
            raise ValueError(f"descriptor payload {len(payload)} exceeds {self.max_bytes} bytes")
        self.output_dir.mkdir(parents=True,exist_ok=True)
        with (self.output_dir/f"step{physical_step:03d}_block025.json").open("xb") as f:
            f.write(payload)
        self.seen.add(physical_step)
        return result
