"""Frozen source-pose geometry and query gains; no model or video decoding."""
import hashlib
import json
import math
from pathlib import Path
import struct

SHAPE = (6, 23, 41)
POSE_SHA = "e0795dc6c9fc652d82b5353f1de18711adffc053920928f2d4687fd195031852"
VIDEO_SHA = "c80a126374966191cf87eebb8b8952d84fc88a7d6a56ca4c8be01a099ca2a857"
SPANS = ((47, 50), (51, 51), (52, 55), (56, 59), (60, 63), (64, 67))
JOINT_PAIRS = ((7, 9), (8, 10))


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def tensor_hash(values):
    flat = [x for frame in values for row in frame for x in row]
    return hashlib.sha256(struct.pack("<" + "f" * len(flat), *flat)).hexdigest()


def distance_to_segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = dx*dx + dy*dy
    frac = 0.0 if norm == 0 else max(0.0, min(1.0,
        ((point[0]-a[0])*dx + (point[1]-a[1])*dy) / norm))
    return math.hypot(point[0] - a[0] - frac*dx, point[1] - a[1] - frac*dy)


def capsule(distance):
    if distance <= 32:
        return 1.0
    if distance >= 64:
        return 0.0
    return 0.5 * (1 + math.cos(math.pi * (distance - 32) / 32))


def pose_at(pose, t):
    lo, hi = math.floor(t), math.ceil(t)
    frames = pose["frames"]
    values = []
    for index in (lo, hi):
        frame = frames[index]
        if frame["frame"] != index or abs(frame["time_s"] - index/24) > 1e-8:
            raise ValueError("source frame indices/timestamps changed")
        if frame["selection_ambiguous"] or frame["selected_person"] is None:
            raise ValueError("missing/ambiguous source pose")
        person = frame["persons"][frame["selected_person"]]
        points = {}
        for joint in (7, 8, 9, 10):
            x, y = person["coco17_xy"][joint]
            score = person["coco17_score"][joint]
            if not all(math.isfinite(v) for v in (x, y, score)) or score < 0.3:
                raise ValueError("invalid source elbow/wrist confidence")
            if not 0 <= x < 1312 or not 0 <= y < 736:
                raise ValueError("source elbow/wrist outside image")
            # DWPose returns pixel-center indices; use pixel-boundary coordinates.
            points[joint] = (x + 0.5, y + 0.5)
        values.append(points)
    weight = t - lo
    return {j: tuple((1-weight)*values[0][j][a] + weight*values[1][j][a]
                     for a in (0, 1)) for j in (7, 8, 9, 10)}


def build_source_mask(pose_path):
    raw = Path(pose_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != POSE_SHA:
        raise ValueError("source pose hash changed")
    pose = json.loads(raw)
    video = pose["video"]
    if (video["sha256"], video["width"], video["height"], video["container_frame_count"],
            video["fps"]) != (VIDEO_SHA, 1312, 736, 141, 24):
        raise ValueError("unsupported source video geometry")
    if pose["joint_order"][7:11] != ["left_elbow", "right_elbow", "left_wrist", "right_wrist"]:
        raise ValueError("COCO joint order changed")
    frames, traces = [], []
    for start, end in SPANS:
        times = sorted(set([float(t) for t in range(start, end+1)] + [(start+end)/2]))
        points = [pose_at(pose, t) for t in times]
        mask = []
        for row in range(23):
            values = []
            for col in range(41):
                center = (32*(col+0.5), 32*(row+0.5))
                d = min(distance_to_segment(center, p[a], p[b])
                        for p in points for a, b in JOINT_PAIRS)
                values.append(f32(capsule(d)))
            mask.append(values)
        frames.append(mask)
        traces.append({"span": [start, end], "times": times, "joint_coordinates": points})
    means = [math.fsum(v for row in frame for v in row)/943 for frame in frames]
    uniform = [[[f32(mean)]*41 for _ in range(23)] for mean in means]
    sums = [{"latent_bin": k+14, "roi_sum": math.fsum(v for row in frame for v in row),
             "uniform_sum": 943*f32(means[k]), "mean_float64": means[k],
             "mean_float32": f32(means[k]), "nonzero_queries": sum(v > 0 for row in frame for v in row)}
            for k, frame in enumerate(frames)]
    if any(abs(r["roi_sum"]-r["uniform_sum"]) > 1e-5 for r in sums):
        raise ValueError("float32 uniform mean exceeds frozen sum tolerance")
    return {"schema": "h3-source-pose-query-mask-v1", "shape": list(SHAPE),
            "source_pose_sha256": POSE_SHA, "source_video_sha256": VIDEO_SHA,
            "source_geometry": [141, 736, 1312], "latent_interval_half_open": [14, 20],
            "position_coverage_inclusive": [47, 67], "inner_px": 32, "outer_px": 64,
            "confidence_min": 0.3, "coordinates": "pixel-boundary: pose xy+0.5, token centers32*(c+0.5,r+0.5)",
            "time_rule": "max over each full nominal span integer frames plus interpolated span center",
            "uniform_rule": "per-bin mean over943 source ROI coefficients; rounded once tofloat32",
            "sum_abs_tolerance": 1e-5, "source_traces": traces, "bin_statistics": sums,
            "roi": frames, "uniform": uniform,
            "tensor_sha256": {"roi": tensor_hash(frames), "uniform": tensor_hash(uniform)}}


class QueryGain:
    """One validated CPU constant and its device copy; unchanged across steps/heads."""
    def __init__(self, values, expected_shape=SHAPE):
        import torch
        tensor = torch.as_tensor(values, device="cpu", dtype=torch.float32).clone().contiguous()
        if tuple(tensor.shape) != tuple(expected_shape):
            raise ValueError("query mask shape mismatch")
        if not bool(torch.isfinite(tensor).all()) or not bool(((tensor >= 0) & (tensor <= 1)).all()):
            raise ValueError("query mask must be finite within[0,1]")
        self.tensor = tensor.reshape(1, 1, -1, 1)
        self.indices = torch.nonzero(tensor.reshape(-1) > 0, as_tuple=False).flatten()
        self.all_zero = len(self.indices) == 0
        self.all_one = bool((tensor == 1).all())
        self._cache = {}

    def on(self, q, rows):
        if rows != self.tensor.shape[2]:
            raise ValueError("query mask length disagrees with actual packed interval")
        key = str(q.device)
        if key not in self._cache:
            self._cache[key] = (self.tensor.to(q.device, copy=True),
                                self.indices.to(q.device, copy=True))
        return self._cache[key]


def load_mask(path, expected_sha, variant):
    if variant not in ("roi", "uniform"):
        raise ValueError("only frozen ROI/uniform variants are supported")
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("mask must be an existing absolute file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("source mask file hash mismatch")
    data = json.loads(raw)
    if (data["schema"], data["shape"], data["source_pose_sha256"], data["source_video_sha256"],
            data["latent_interval_half_open"], data["inner_px"], data["outer_px"]) != (
            "h3-source-pose-query-mask-v1", list(SHAPE), POSE_SHA, VIDEO_SHA, [14,20], 32, 64):
        raise ValueError("source mask frozen contract mismatch")
    if tensor_hash(data[variant]) != data["tensor_sha256"][variant]:
        raise ValueError("mask values disagree with tensor hash")
    return QueryGain(data[variant]), {k:v for k,v in data.items() if k not in ("roi","uniform","source_traces")}
