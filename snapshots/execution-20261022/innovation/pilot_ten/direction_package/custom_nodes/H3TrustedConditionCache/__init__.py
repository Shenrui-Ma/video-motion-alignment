"""Load locally registered historical conditioning with pinned SHA256 identities."""
import hashlib
import json
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):
            h.update(block)
    return h.hexdigest()

def signature(tensor):
    import torch
    value=tensor.detach().to(device='cpu').contiguous()
    return {'shape':list(value.shape),'dtype':str(value.dtype),
            'sha256':hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}

def checked_tensor(record):
    import torch
    path=Path(record['file'])
    if path.is_symlink() or sha(path)!=record['sha256']:
        raise ValueError('cached tensor file identity differs')
    value=torch.load(path,map_location='cpu',weights_only=True)
    if not isinstance(value,torch.Tensor) or signature(value)!=record['tensor_signature']:
        raise ValueError('cached tensor values/dtype/shape differ')
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


class H3TrustedConditionCache:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'cache_manifest':('STRING',),'manifest_sha256':('STRING',)}}
    RETURN_TYPES=('CONDITIONING','LATENT')
    FUNCTION='load'
    CATEGORY='research/H3TrustedCache'

    @classmethod
    def IS_CHANGED(cls, cache_manifest, manifest_sha256):
        return float('nan')

    def load(self,cache_manifest,manifest_sha256):
        path=Path(cache_manifest)
        if path.is_symlink() or sha(path)!=manifest_sha256:
            raise ValueError('registered cache manifest changed')
        manifest=json.loads(path.read_text())
        if manifest['schema'] not in {'r146-original-clean-condition-cache-v1','r144-original-clean-condition-cache-v1'}:
            raise ValueError('unsupported conditioning cache schema')
        if sha(manifest['source_video'])!=manifest['source_video_sha256']:
            raise ValueError('reference video binding changed')
        positive,target,_,_=reconstruct(manifest)
        return positive,target

NODE_CLASS_MAPPINGS={'H3TrustedConditionCache':H3TrustedConditionCache}
