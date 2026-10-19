"""Read-only, per-run checks of one shared H3 conditioning computation."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re


def _safe_id(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) or value in {".", ".."}:
        raise ValueError("audit identifiers must be simple filename components")
    return value


def _tensor_info(tensor):
    # Match H3EventAudit's byte identity, including bfloat16, without mutations.
    import torch

    cpu = tensor.detach().to("cpu").contiguous()
    return {"shape": list(cpu.shape), "dtype": str(cpu.dtype),
            "sha256": hashlib.sha256(cpu.view(torch.uint8).numpy().data).hexdigest()}


def _verify_tensor(label, tensor, expected):
    actual = _tensor_info(tensor)
    if actual != {key: expected[key] for key in ("shape", "dtype", "sha256")}:
        raise ValueError(f"shared conditioning mismatch: {label}")
    return actual


class H3PairConditionSnapshot:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "positive": ("CONDITIONING",),
            "target": ("LATENT",),
            "source_audit_dir": ("STRING",),
            "source_run_id": ("STRING", {"default": "unbound_shared"}),
            "run_id": ("STRING", {"default": "unbound_run"}),
        }}

    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "target_latent")
    FUNCTION = "snapshot"
    CATEGORY = "research/MiniMax H3"

    def snapshot(self, positive, target, source_audit_dir, source_run_id, run_id):
        from comfy.ldm.minimax.model import PackedLayout

        _safe_id(source_run_id)
        _safe_id(run_id)
        if source_run_id == run_id:
            raise ValueError("a snapshot must not overwrite the shared source manifest")
        from r107_contract import validate_job, audit_dir
        row=validate_job(run_id)
        root=audit_dir(source_audit_dir)
        if source_run_id != 'r107_'+row['case']['source_id']+'_shared':
            raise ValueError('R107 source-conditioning identity mismatch')
        source_path = root / (source_run_id + "_conditioning.json")
        source_bytes = source_path.read_bytes()
        common = json.loads(source_bytes)
        if common.get("schema") != "h3-event-audit-v1" or common.get("run_id") != source_run_id:
            raise ValueError("unexpected shared conditioning manifest identity")
        if len(positive) != 1:
            raise ValueError("snapshot supports one unscheduled conditioning entry")
        embedding, meta = positive[0]
        if meta.get("minimax_keyframes"):
            raise ValueError("keyframes are outside this reference-only snapshot")
        actual_embedding = _verify_tensor("embedding", embedding, common["conditioning_embedding"])
        actual_tags = _verify_tensor("token_tags", meta["minimax_token_tags"], common["token_tags"])

        refs = meta["minimax_refs"]
        calls = common["native_vae_calls"]
        if not refs or len(refs) != len(calls):
            raise ValueError("reference count differs from shared native VAE calls")
        actual_refs = []
        # The native node emits visual references in the same order as VAE calls.
        for index, (ref, call) in enumerate(zip(refs, calls)):
            kind = ref["kind"]
            if kind not in ("image", "video") or ref.get("ref_audio_t", 0) != 0 or ref.get("audio_latent") is not None:
                raise ValueError("snapshot supports only silent video and image references")
            latent = _verify_tensor(f"reference {index}", ref["latent"], call["latent"])
            expected_shape = [1, 24, 1 if kind == "image" else ref["latent_t"],
                              ref["latent_h"], ref["latent_w"]]
            if latent["shape"] != expected_shape:
                raise ValueError(f"reference {index} metadata disagrees with clean latent")
            actual_refs.append({"reference_index": index, "kind": kind,
                                "source_vae_call_index": index, "clean_latent": latent})

        streams = target["samples"].unbind()
        shapes = [list(stream.shape) for stream in streams]
        if len(streams) != 2 or shapes != common["target_latent_shapes"]:
            raise ValueError("target latent shapes differ from the shared manifest")
        video, audio = streams
        layout = PackedLayout(embedding.shape[1], *video.shape[2:], audio.shape[-1], refs=refs)
        expected_layout = common["packed_layout"]
        segments = [list(segment) for segment in layout.segments]
        if layout.seq_len != expected_layout["seq_len"] or segments != expected_layout["segments"]:
            raise ValueError("packed layout differs from the shared manifest")
        position_ids = _verify_tensor("position_ids", layout.position_ids, expected_layout["position_ids"])

        manifest = deepcopy(common)
        manifest["run_id"] = run_id
        manifest["pair_snapshot"] = {
            "schema": "h3-pair-condition-snapshot-v1", "verified": True,
            "source_run_id": source_run_id, "source_manifest": source_path.name,
            "source_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "preprocessing_provenance": "Copied from the shared source computation; this node does not encode or tokenize.",
            "tensor_file_base": ".",
            "cache_usage": {
                "assumption": "Identical shared node inputs permit Comfy cache reuse across benchmark and paired runs.",
                "verified": False,
                "required_evidence": "Check shared node 5 in each prompt history execution_cached event.",
            },
            "actual": {
                "conditioning_embedding": actual_embedding, "token_tags": actual_tags,
                "references": actual_refs, "target_latent_shapes": shapes,
                "target_latent_dtypes": [str(stream.dtype) for stream in streams],
                "packed_layout": {"seq_len": layout.seq_len, "segments": segments,
                                  "position_ids": position_ids},
            },
        }
        from parent_evidence import validate_parent_condition
        proof = validate_parent_condition(manifest, row["source_id"])
        proof_path = root / (run_id + "_parent_condition_match.json")
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        path = root / (run_id + "_conditioning.json")
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return positive, target


NODE_CLASS_MAPPINGS = {"H3PairConditionSnapshot": H3PairConditionSnapshot}
NODE_DISPLAY_NAME_MAPPINGS = {name: name for name in NODE_CLASS_MAPPINGS}
