"""Diagnostic swap of one native H3 Ref2VA direct image-latent branch.

Qwen contextualizes the entire condition jointly. Keeping the base embeddings
while taking a donor VAE reference latent creates a hybrid conditioning path;
it does not isolate a pure identity representation or identify background tokens.
Only native, unscheduled Ref2VA metadata is supported. No tensor is modified.
"""

import torch


_METADATA_KEYS = {"pooled_output", "minimax_token_tags", "minimax_refs"}
_REF_KEYS = {
    "image": {"kind", "latent_h", "latent_w", "latent"},
    "video": {"kind", "latent_t", "latent_h", "latent_w", "ref_audio_t", "latent", "audio_latent"},
    "video_audio": {"kind", "latent_t", "latent_h", "latent_w", "ref_audio_t", "latent", "audio_latent"},
    "audio": {"kind", "ref_audio_t", "audio_latent"},
}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _tensor_pair(base, donor, label, equal=False):
    _require(isinstance(base, torch.Tensor) and isinstance(donor, torch.Tensor),
             f"{label}: expected tensors")
    _require(base.shape == donor.shape, f"{label}: shape mismatch")
    _require(base.dtype == donor.dtype and base.device == donor.device,
             f"{label}: dtype/device mismatch")
    if equal:
        _require(base is donor or torch.equal(base, donor), f"{label}: values differ")


def _validate_ref(ref, label):
    _require(isinstance(ref, dict), f"{label}: expected reference dict")
    kind = ref.get("kind")
    _require(kind in _REF_KEYS, f"{label}: unsupported reference kind")
    _require(set(ref) == _REF_KEYS[kind], f"{label}: unsupported reference metadata")
    for key in ("latent_t", "latent_h", "latent_w", "ref_audio_t"):
        if key in ref:
            _require(type(ref[key]) is int and ref[key] >= (0 if key == "ref_audio_t" else 1),
                     f"{label}: invalid {key}")
    if kind != "audio":
        latent = ref["latent"]
        _require(isinstance(latent, torch.Tensor) and latent.ndim == 5,
                 f"{label}: expected 5-D video VAE latent")
        _require(tuple(latent.shape[-2:]) == (ref["latent_h"], ref["latent_w"]),
                 f"{label}: spatial geometry does not match latent")
        _require(latent.shape[2] == (1 if kind == "image" else ref["latent_t"]),
                 f"{label}: temporal geometry does not match latent")
    if kind != "image":
        audio = ref["audio_latent"]
        if kind == "video":
            _require(ref["ref_audio_t"] == 0 and audio is None,
                     f"{label}: silent video has audio payload")
        else:
            _require(isinstance(audio, torch.Tensor) and audio.ndim == 4
                     and audio.shape[-1] == ref["ref_audio_t"] and ref["ref_audio_t"] > 0,
                     f"{label}: invalid audio geometry")


def swap_reference_latent(base_conditioning, donor_conditioning, reference_image_index):
    """Return fresh list/dict containers, sharing base tensors except one latent."""
    _require(type(reference_image_index) is int and reference_image_index >= 0,
             "reference_image_index must be a nonnegative, zero-based image ordinal")
    _require(isinstance(base_conditioning, (list, tuple))
             and isinstance(donor_conditioning, (list, tuple))
             and len(base_conditioning) == len(donor_conditioning) > 0,
             "conditioning entry counts must match and be nonempty")
    result = []
    for entry_index, (base_entry, donor_entry) in enumerate(zip(base_conditioning, donor_conditioning)):
        label = f"conditioning[{entry_index}]"
        _require(isinstance(base_entry, (list, tuple)) and len(base_entry) == 2
                 and isinstance(donor_entry, (list, tuple)) and len(donor_entry) == 2,
                 f"{label}: expected [embedding, metadata]")
        base_embedding, base_meta = base_entry
        donor_embedding, donor_meta = donor_entry
        _tensor_pair(base_embedding, donor_embedding, f"{label} embedding")
        _require(base_embedding.ndim == 3, f"{label}: expected 3-D embedding")
        _require(isinstance(base_meta, dict) and isinstance(donor_meta, dict),
                 f"{label}: expected metadata dicts")
        _require(set(base_meta) == set(donor_meta)
                 and set(base_meta) <= _METADATA_KEYS
                 and {"minimax_token_tags", "minimax_refs"} <= set(base_meta),
                 f"{label}: unsupported or mismatched conditioning metadata")
        tags = base_meta["minimax_token_tags"]
        _tensor_pair(tags, donor_meta["minimax_token_tags"], f"{label} token tags", equal=True)
        _require(tags.ndim == 1 and tags.shape[0] == base_embedding.shape[1]
                 and tags.dtype == torch.long and bool(((tags == 0) | (tags == 1)).all()),
                 f"{label}: invalid token tags")
        if "pooled_output" in base_meta:
            bp, dp = base_meta["pooled_output"], donor_meta["pooled_output"]
            if bp is not None or dp is not None:
                _tensor_pair(bp, dp, f"{label} pooled output")
        base_refs, donor_refs = base_meta["minimax_refs"], donor_meta["minimax_refs"]
        _require(isinstance(base_refs, list) and isinstance(donor_refs, list)
                 and len(base_refs) == len(donor_refs), f"{label}: reference counts mismatch")
        image_ordinal = 0
        found = False
        refs = []
        for ref_index, (base_ref, donor_ref) in enumerate(zip(base_refs, donor_refs)):
            ref_label = f"{label} reference[{ref_index}]"
            _validate_ref(base_ref, ref_label + " base")
            _validate_ref(donor_ref, ref_label + " donor")
            _require(base_ref["kind"] == donor_ref["kind"], f"{ref_label}: kind/order mismatch")
            selected = base_ref["kind"] == "image" and image_ordinal == reference_image_index
            for key, value in base_ref.items():
                other = donor_ref[key]
                if isinstance(value, torch.Tensor) or isinstance(other, torch.Tensor):
                    _tensor_pair(value, other, f"{ref_label} {key}",
                                 equal=not (selected and key == "latent"))
                else:
                    _require(value == other, f"{ref_label}: {key} geometry/metadata mismatch")
            copied = dict(base_ref)
            if selected:
                copied["latent"] = donor_ref["latent"]
                found = True
            refs.append(copied)
            image_ordinal += base_ref["kind"] == "image"
        _require(found, f"{label}: reference_image_index out of range")
        metadata = dict(base_meta)
        metadata["minimax_refs"] = refs
        result.append([base_embedding, metadata])
    return result


class H3ReferenceBranchSwap:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "base_conditioning": ("CONDITIONING",),
            "donor_conditioning": ("CONDITIONING",),
            "reference_image_index": ("INT", {"default": 0, "min": 0}),
        }}

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "swap"
    CATEGORY = "research/MiniMax H3"

    def swap(self, base_conditioning, donor_conditioning, reference_image_index=0):
        return (swap_reference_latent(base_conditioning, donor_conditioning, reference_image_index),)


NODE_CLASS_MAPPINGS = {"H3ReferenceBranchSwap": H3ReferenceBranchSwap}
NODE_DISPLAY_NAME_MAPPINGS = {"H3ReferenceBranchSwap": "H3 Reference Branch Swap (Diagnostic)"}
