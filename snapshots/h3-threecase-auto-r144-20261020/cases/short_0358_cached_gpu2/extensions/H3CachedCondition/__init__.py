"""Exact historical clean conditioning, with no Qwen or reference VAE execution."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def signature(value):
    import importlib.util
    import sys
    path = Path(__file__).resolve().parent.parent / "H3X0Readout/core.py"
    name = "_h3_cached_readout_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return {key: entry for key, entry in sys.modules[name].tensor_signature(value).items() if key != "bytes"}


def checked_tensor(record):
    import torch
    path = Path(record["file"])
    if path.is_symlink() or sha(path) != record["sha256"]:
        raise ValueError("cached tensor file identity differs")
    value = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(value, torch.Tensor) or signature(value) != record["tensor_signature"]:
        raise ValueError("cached tensor values/dtype/shape differ")
    return value


def reconstruct(manifest):
    """Rebuild only the exact unscheduled, single silent video reference contract."""
    import torch
    from comfy_extras.nodes_minimax_h3 import _empty_av_latent
    from comfy.ldm.minimax.model import PackedLayout
    source = manifest["conditioning"]
    if sha(source["file"]) != source["sha256"]:
        raise ValueError("historical conditioning metadata changed")
    old = json.loads(Path(source["file"]).read_text())
    if old["schema"] != "h3-event-audit-v1" or old["run_id"] != manifest["shared_run_id"]:
        raise ValueError("unexpected source conditioning identity")
    if hashlib.sha256(old["prompt"].encode()).hexdigest() != manifest["prompt_sha256"]:
        raise ValueError("original prompt changed")
    if len(old["native_vae_calls"]) != 1 or len(old["qwen_presentation"]) != 1:
        raise ValueError("requires exactly one original silent video")
    cache = {row["role"]: checked_tensor(row) for row in manifest["tensors"]}
    if set(cache) != {"reference_vae_latent", "conditioning_embedding", "conditioning_tags", "conditioning_position"}:
        raise ValueError("four exact cache roles required")
    latent = cache["reference_vae_latent"]
    embedding, tags, positions = (cache[name] for name in
                                  ("conditioning_embedding", "conditioning_tags", "conditioning_position"))
    for actual, expected in ((latent, old["native_vae_calls"][0]["latent"]),
                             (embedding, old["conditioning_embedding"]), (tags, old["token_tags"]),
                             (positions, old["packed_layout"]["position_ids"])):
        if signature(actual) != {key: expected[key] for key in ("shape", "dtype", "sha256")}:
            raise ValueError("cache differs from actual historical conditioning")
    g = manifest["geometry"]
    target, count = _empty_av_latent(g["width"], g["height"], g["frames"])
    video, audio = target["samples"].unbind()
    if count != g["frames"] or [list(x.shape) for x in (video, audio)] != old["target_latent_shapes"]:
        raise ValueError("target geometry differs")
    if any(x.dtype != torch.float32 or torch.count_nonzero(x) for x in (video, audio)):
        raise ValueError("original float32 zero target required")
    refs = [{"kind": "video", "latent_t": latent.shape[2], "latent_h": latent.shape[3],
             "latent_w": latent.shape[4], "ref_audio_t": 0, "latent": latent, "audio_latent": None}]
    # Frozen MiniMaxQwen3VL returns (hidden_state, None), no pooled or attention-mask tensor.
    # Original CLIPLoader has no hooks or schedules. Verified by CPU native-node structural replay.
    positive = [[embedding, {"pooled_output": None, "minimax_token_tags": tags, "minimax_refs": refs}]]
    layout = PackedLayout(embedding.shape[1], *video.shape[2:], audio.shape[-1], refs=refs)
    if (layout.seq_len != old["packed_layout"]["seq_len"]
            or [list(v) for v in layout.segments] != old["packed_layout"]["segments"]
            or not torch.equal(layout.position_ids, positions)):
        raise ValueError("original packed position values/layout differ")
    return positive, target, old, cache


def publish_metadata(manifest, old, audit_root):
    """Hardlink immutable historical evidence; no RGB allocation or copying."""
    root = Path(audit_root)
    parent = Path(manifest["parent_root"]) / "audit"
    def visit(value):
        if isinstance(value, dict):
            if "tensor_file" in value:
                relative = Path(value["tensor_file"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("unsafe tensor evidence path")
                origin, target = parent / relative, root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    os.link(origin, target)
                if not os.path.samefile(origin, target):
                    raise ValueError("cached evidence must be the same immutable file")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(old)
    path = root / (manifest["shared_run_id"] + "_conditioning.json")
    data = deepcopy(old)
    # Preserve old numerical metadata exactly; provenance belongs in a separate receipt.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


class H3CachedReferenceConditioning:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"cache_manifest": ("STRING",), "audit_dir": ("STRING",), "run_id": ("STRING",)}}

    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "target_latent")
    FUNCTION = "load"
    CATEGORY = "research/MiniMax H3"

    def load(self, cache_manifest, audit_dir, run_id):
        from r86_contract import ROOT, validate_job, audit_dir as checked_audit
        row = validate_job(run_id)
        path = Path(cache_manifest)
        if path != ROOT / "configs/CONDITION_CACHE.json":
            raise ValueError("unregistered cache manifest")
        manifest = json.loads(path.read_text())
        case = row["case"]
        if (manifest["source_id"] != case["source_id"] or manifest["seed"] != case["seed"]
                or manifest["geometry"] != case["geometry"]):
            raise ValueError("cached source/seed/geometry mismatch")
        if sha(ROOT / "inputs" / case["video"]) != manifest["source_video_sha256"]:
            raise ValueError("cached source MP4 binding differs")
        positive, target, old, _ = reconstruct(manifest)
        root = checked_audit(audit_dir)
        publish_metadata(manifest, old, root)
        receipt = {
            "schema": "r144-exact-clean-conditioning-cache-v1", "run_id": run_id,
            "manifest_sha256": sha(path), "historical_shared_run": manifest["shared_run_id"],
            "prompt_sha256": manifest["prompt_sha256"], "source_video_sha256": manifest["source_video_sha256"],
            "actual_tensors_exact": True, "reference_encoder_calls": 0, "text_encoder_calls": 0,
            "RGB_tensor_allocations": 0, "packed_layout_exact": True,
            "cache_files": manifest["tensors"],
        }
        (root / "CACHED_CONDITION_RUNTIME.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return positive, target


NODE_CLASS_MAPPINGS = {"H3CachedReferenceConditioning": H3CachedReferenceConditioning}
NODE_DISPLAY_NAME_MAPPINGS = {"H3CachedReferenceConditioning": "H3 exact historical clean conditioning"}
