"""Read-only contract derived from every actual Ref2VA attention module."""


def architecture_contract(diffusion):
    if len(diffusion.blocks) != 50 or getattr(diffusion, "hidden_size", None) != 5376:
        raise ValueError("R17 requires actual Ref2VA hidden5376 / 50 blocks")
    layers = []
    for index, block in enumerate(diffusion.blocks):
        attn = block.attn
        heads, dim = getattr(attn, "heads", None), getattr(attn, "head_dim", None)
        if type(heads) is not int or heads < 1 or type(dim) is not int or dim != 128:
            raise ValueError(f"block{index}: invalid actual attention heads/head_dim {heads}/{dim}")
        if layers and heads != layers[0]["heads"]:
            raise ValueError(f"block{index}: attention head count differs from earlier blocks")
        inner = heads * dim
        sizes = (attn.qkv_proj.in_features, attn.qkv_proj.out_features,
                 attn.out_proj.in_features, attn.out_proj.out_features)
        if sizes != (5376, inner * 3, inner, 5376):
            raise ValueError(f"block{index}: unexpected QKV/output projection dimensions {sizes}")
        if "forward" in vars(attn):
            raise ValueError(f"block{index}: instance attention.forward override unsupported")
        layers.append({"index": index, "heads": heads, "head_dim": dim,
                       "projection_sizes": list(sizes),
                       "attention_class": f"{type(attn).__module__}.{type(attn).__qualname__}"})
    return {"hidden_size": diffusion.hidden_size, "num_blocks": len(layers),
            "heads": layers[0]["heads"], "head_dim": layers[0]["head_dim"],
            "attention_inner": layers[0]["heads"] * layers[0]["head_dim"],
            "layers": layers, "source": "actual diffusion.blocks[i].attn attributes, all50 checked"}
