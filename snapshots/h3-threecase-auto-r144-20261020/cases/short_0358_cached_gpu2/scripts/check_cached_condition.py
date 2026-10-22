"""CPU replay of native reference assembly with verified archived encoder outputs."""
import copy
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "extensions")]
from r86_contract import read, require, sha
from execution_gate import atomic


def equal_tree(left, right):
    import torch
    if isinstance(left, torch.Tensor):
        return isinstance(right, torch.Tensor) and left.dtype == right.dtype and left.shape == right.shape and torch.equal(left, right)
    if type(left) != type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_tree(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(equal_tree(a, b) for a, b in zip(left, right))
    return left == right


def main():
    runtime = read(ROOT / "configs/runtime.json")
    require(str(ROOT) == runtime["remote_root"] and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "remote CPU check only")
    sys.path[:0] = [runtime["dependencies"], runtime["core"]]
    import torch
    torch.set_num_threads(4)
    from compatibility_bootstrap import install, install_video_compat
    install()
    install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
    from H3CachedCondition import reconstruct, signature
    started = time.time()
    manifest = read(ROOT / "configs/CONDITION_CACHE.json")
    positive, target, old, cache = reconstruct(manifest)
    parent = Path(manifest["parent_root"]) / "audit"
    prepared = old["native_vae_calls"][0]["prepared_frames"]
    frames = torch.load(parent / prepared["tensor_file"], map_location="cpu", weights_only=True, mmap=True)
    require(signature(frames) == {k: prepared[k] for k in ("shape", "dtype", "sha256")}, "actual historical prepared RGB changed")
    called = {"encode": 0, "tokenize": 0, "embedding": 0}

    class VerifiedVAEOutput:
        def encode(self, value):
            called["encode"] += 1
            require(signature(value) == signature(frames), "native reference assembly changed RGB")
            return cache["reference_vae_latent"]

    class VerifiedQwenOutput:
        def tokenize(self, prompt, **kwargs):
            called["tokenize"] += 1
            require(prompt == old["prompt"] and set(kwargs) == {"minimax_ref_items"}, "native prompt/presentation changed")
            items = kwargs["minimax_ref_items"]
            require(len(items) == 1 and items[0]["type"] == "video", "native reference inventory changed")
            expected = old["qwen_presentation"][0]
            require(items[0]["timestamps"] == expected["sampling"]["sample_timestamps_seconds"], "Qwen time sampling changed")
            require(signature(items[0]["data"]) == {k: expected["actual_sampled_frames"][k] for k in ("shape", "dtype", "sha256")}, "Qwen presentation RGB changed")
            return "verified_original_presentation"

        def encode_from_tokens_scheduled(self, tokens):
            called["embedding"] += 1
            require(tokens == "verified_original_presentation", "unexpected presentation")
            return [[cache["conditioning_embedding"], {"pooled_output": None, "minimax_token_tags": cache["conditioning_tags"]}]]

    g = manifest["geometry"]
    # The archived tensor is already the original prepared RGB. The original
    # resize can change values even at equal dimensions; do not resize it twice.
    from unittest.mock import patch
    def verified_prepared(value, width, height, crop):
        require(value is frames and (width, height, crop) == (g["width"], g["height"], "disabled"), "prepared RGB assembly contract differs")
        return frames
    with patch("comfy_extras.nodes_minimax_h3._resize", side_effect=verified_prepared):
      native = MiniMaxH3ReferenceToVideo.execute(
        clip=VerifiedQwenOutput(), vae=VerifiedVAEOutput(), prompt=old["prompt"],
        width=g["width"], height=g["height"], length=g["frames"],
        ref_image_size="match", ref_images=None, ref_videos={"ref_video_0": frames})
    require(equal_tree(positive, native[0]), "cached positive tree differs from native assembly")
    require(equal_tree(target["samples"].unbind(), native[1]["samples"].unbind()), "cached zero target differs from native assembly")
    require(called == {"encode": 1, "tokenize": 1, "embedding": 1}, "structural replay coverage changed")
    require(not torch.cuda.is_initialized(), "CPU proof initialized CUDA")
    sources = {}
    for relative in ("comfy_extras/nodes_minimax_h3.py", "comfy/sd.py", "comfy/sd1_clip.py",
                     "comfy/text_encoders/minimax.py", "comfy/text_encoders/qwen3vl.py",
                     "comfy/text_encoders/llama.py", "comfy/ldm/minimax/model.py"):
        sources[relative] = sha(Path(runtime["core"]) / relative)
    result = {
        "schema": "r144-exact-cache-native-assembly-cpu-v1", "passed": True,
        "cache_manifest_sha256": sha(ROOT / "configs/CONDITION_CACHE.json"),
        "positive_tree_equal": True, "target_tree_equal": True, "packed_layout_exact": True,
        "tensor_shape_dtype_values_exact": True,
        "native_assembly_function": "MiniMaxH3ReferenceToVideo.execute",
        "encoder_output_source": "verified original serialized tensors; no neural encoder execution",
        "preprocessing_replay_scope": "Original archived prepared RGB is supplied at the resize boundary; no repeated pixel preprocessing",
        "original_input_RGB_equals_prepared_RGB": old["input_video"]["sha256"] == prepared["sha256"],
        "pooled_output": None, "metadata_keys": sorted(positive[0][1]),
        "source_files": sources, "CUDA_initialized": False, "neural_model_loads": 0,
        "actual_encoder_calls": 0, "structural_replay_stub_calls": called,
        "CPU_peak_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "elapsed_seconds": time.time() - started,
    }
    atomic(ROOT / "audit/CACHED_CONDITION_CPU_PROOF.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
