"""Task-local Torch 2.5 schema-annotation compatibility for comfy_kitchen.

Usage: python compatibility_bootstrap.py /isolated/ComfyUI/main.py [Comfy args]
CPU check: python compatibility_bootstrap.py --check /isolated/ComfyUI

Task-local adapters normalize schema annotations and bridge PyAV16 video APIs.
For this experiment, oversized Triton INT8 linear calls are additionally split
into independent row chunks to avoid signed-32 offset overflow. Checkpoints,
attention, sampler and shared installed files are unchanged. The row adapter
is inference-only and delegates each chunk to the original numerical operator.
"""
from pathlib import Path
from enum import IntEnum
import importlib.abc
import importlib.machinery
import runpy
import sys
import types
import typing


def normalize(annotation):
    if annotation is type(None):
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if not args:
        return annotation
    converted = tuple(normalize(arg) for arg in args)
    if origin is list:
        return typing.List[converted[0]]
    if origin is tuple:
        return typing.Tuple[converted]
    if origin in (types.UnionType, typing.Union):
        return typing.Union[converted]
    return annotation


def install():
    import torch
    original = torch.library.infer_schema
    if getattr(original, "_h3_annotation_compat", False):
        return

    def infer_schema(function, *args, **kwargs):
        if not getattr(function, "__module__", "").startswith("comfy_kitchen."):
            return original(function, *args, **kwargs)
        old = function.__annotations__
        resolved = typing.get_type_hints(function)
        new = {name: normalize(annotation) for name, annotation in resolved.items()}
        if old == new:
            return original(function, *args, **kwargs)
        function.__annotations__ = new
        try:
            return original(function, *args, **kwargs)
        finally:
            function.__annotations__ = old

    infer_schema._h3_annotation_compat = True
    torch.library.infer_schema = infer_schema


def install_video_compat():
    """Expose PyAV17 enum names and support only 8-bit SDR on existing PyAV16.

    Pixel conversion, tensor construction, reformat calls, and encode calls
    remain the native Core implementation. Codec contexts retain all metadata;
    old VideoFrame objects receive only properties their API supports.
    """
    import av
    import av.video.reformatter as reformatter
    if hasattr(reformatter, "ColorPrimaries") and hasattr(reformatter, "ColorTrc"):
        return
    if not av.__version__.startswith("16."):
        raise RuntimeError("Only verified PyAV16 compatibility is supported")
    # Values read from the real PyAV17 enums on the known-good .41 runtime.
    reformatter.ColorPrimaries = IntEnum("ColorPrimaries", {
        "BT709": 1, "UNSPECIFIED": 2, "BT470M": 4, "BT470BG": 5,
        "SMPTE170M": 6, "SMPTE240M": 7, "FILM": 8, "BT2020": 9,
        "SMPTE428": 10, "SMPTE431": 11, "SMPTE432": 12, "EBU3213": 22})
    reformatter.ColorTrc = IntEnum("ColorTrc", {
        "BT709": 1, "UNSPECIFIED": 2, "GAMMA22": 4, "GAMMA28": 5,
        "SMPTE170M": 6, "SMPTE240M": 7, "LINEAR": 8, "LOG": 9,
        "LOG_SQRT": 10, "IEC61966_2_4": 11, "BT1361_ECG": 12,
        "IEC61966_2_1": 13, "BT2020_10": 14, "BT2020_12": 15,
        "SMPTE2084": 16, "SMPTE428": 17, "ARIB_STD_B67": 18})

    def patch(module):
        original_set = module.set_video_color_properties
        original_copy = module.copy_color_properties
        original_components = module.VideoFromFile.get_components_internal
        original_init = module.VideoFromComponents.__init__

        def require_sdr(source):
            fmt = getattr(source, "format", None)
            components = getattr(fmt, "components", ())
            if any(c.bits > 8 for c in components):
                raise ValueError("Task PyAV16 compatibility supports only 8-bit SDR")
            if getattr(source, "color_trc", None) in (14, 15, 16, 18) or getattr(source, "color_primaries", None) == 9:
                raise ValueError("Task PyAV16 compatibility rejects HDR/wide-gamut input")

        def set_properties(target, color_space):
            if color_space != "sRGB":
                raise ValueError("Task PyAV16 compatibility supports only sRGB output")
            if isinstance(target, av.VideoFrame):
                require_sdr(target)
                target.colorspace = module.BT709_NCL
                target.color_range = reformatter.ColorRange.MPEG
            else:
                original_set(target, color_space)

        def copy_properties(source, target):
            require_sdr(source)
            if isinstance(target, av.VideoFrame):
                require_sdr(target)
                target.colorspace = source.colorspace
                target.color_range = source.color_range
            else:
                original_copy(source, target)

        def get_components(instance, container):
            require_sdr(instance._get_first_video_stream(container))
            return original_components(instance, container)

        def components_init(instance, components, bit_depth=8, color_space="sRGB"):
            if bit_depth != 8 or color_space != "sRGB":
                raise ValueError("Task PyAV16 compatibility supports only 8-bit sRGB")
            original_init(instance, components, bit_depth=bit_depth, color_space=color_space)

        module.set_video_color_properties = set_properties
        module.copy_color_properties = copy_properties
        module.VideoFromFile.get_components_internal = get_components
        module.VideoFromComponents.__init__ = components_init

    target_name = "comfy_api.latest._input_impl.video_types"

    class Loader(importlib.abc.Loader):
        def __init__(self, original):
            self.original = original
        def create_module(self, spec):
            return self.original.create_module(spec)
        def exec_module(self, module):
            self.original.exec_module(module)
            patch(module)

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname != target_name:
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec is not None:
                spec.loader = Loader(spec.loader)
            return spec

    if target_name in sys.modules:
        patch(sys.modules[target_name])
    else:
        sys.meta_path.insert(0, Finder())


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    checking = sys.argv[1] == "--check"
    entry = Path(sys.argv[2] if checking else sys.argv[1]).resolve()
    core = entry if checking else entry.parent
    sys.path.insert(0, str(core))
    if not checking:
        from startup_barrier import wait_for_release
        wait_for_release(Path(__file__).resolve().parents[1])
    install()
    install_video_compat()
    if checking:
        import torch
        import comfy.cli_args
        comfy.cli_args.args.cpu = True
        comfy.cli_args.args.disable_xformers = True
        import comfy_kitchen
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        print("CPU imports passed", torch.__version__, comfy_kitchen.__file__)
    else:
        sys.argv = [str(entry)] + sys.argv[2:]
        if "--enable-triton-backend" not in sys.argv:
            raise RuntimeError("This task's INT8 row guard requires the frozen Triton backend flag")
        from int8_row_chunking import install as install_int8_row_guard
        import json
        guard = install_int8_row_guard(log_path=Path(__file__).resolve().parents[1] / "logs/int8_row_chunking.jsonl")
        print("H3_TASK_INT8_ROW_GUARD=" + json.dumps(guard), flush=True)
        from backend_dispatch_audit import install as install_backend_dispatch_audit
        dispatch = install_backend_dispatch_audit(
            log_path=Path(__file__).resolve().parents[1] / "logs/backend_dispatch_audit.json")
        print("H3_TASK_BACKEND_DISPATCH_AUDIT=" + json.dumps(dispatch), flush=True)
        runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
