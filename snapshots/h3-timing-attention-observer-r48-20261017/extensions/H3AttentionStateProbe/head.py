import torch
from .source import require

def output_head_contract(final_layer):
    """Freeze the Ref2VA single-head shapes and the actual loaded float dtype."""
    heads = {}
    for name, width in (('video_out', 96), ('audio_out', 32)):
        head = getattr(final_layer, name, None)
        kind = type(head)
        mixed_linear = (isinstance(head, torch.nn.Module) and kind.__module__ == 'comfy.ops' and
                        kind.__qualname__ == 'mixed_precision_ops.<locals>.MixedPrecisionOps.Linear')
        require(isinstance(head, torch.nn.Linear) or mixed_linear,
                'expected official Linear output head: ' + name)
        require(head.in_features == 5376 and head.out_features == width and
                tuple(head.weight.shape) == (width, 5376) and head.bias is not None and
                tuple(head.bias.shape) == (width,), 'frozen output head shape changed: ' + name)
        require(head.weight.dtype in (torch.float16, torch.bfloat16, torch.float32) and
                head.bias.dtype == head.weight.dtype,
                'frozen output head dtype changed: ' + name)
        require(getattr(head, 'quant_format', None) is None and getattr(head, 'layout_type', None) is None,
                'frozen output head must be nonquantized: ' + name)
        heads[name] = {'weight_shape': list(head.weight.shape), 'bias_shape': list(head.bias.shape),
                       'in_features': head.in_features, 'out_features': head.out_features,
                       'class_module': kind.__module__, 'class_qualname': kind.__qualname__,
                       'weight_dtype': str(head.weight.dtype), 'bias_dtype': str(head.bias.dtype)}
    return {'head_mode': 'single_linear', 'pdd_active': False, 'bank_size': 1, 'heads': heads}
