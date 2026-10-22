"""CPU integration test for this task's restricted PyAV16 compatibility."""
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(os.environ["H3_TASK_ROOT"])
sys.path.insert(0, str(root / "ComfyUI"))
spec = importlib.util.spec_from_file_location("compat", root / "scripts/compatibility_bootstrap.py")
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)
compat.install()
compat.install_video_compat()
import comfy.cli_args
comfy.cli_args.args.cpu = True
comfy.cli_args.args.disable_xformers = True
import av
import numpy as np
import torch
torch.set_num_threads(2)
from comfy_api.latest._input_impl.video_types import VideoFromFile, VideoFromComponents, set_video_color_properties
from comfy_extras.nodes_video import CreateVideo

source = root / "input/01_walk_look_up.mp4"
components = VideoFromFile(str(source)).get_components()
images = components.images
assert len(images) == 107, images.shape
assert float(components.frame_rate) == 24
count = 0
max_diff = 0.0
with av.open(str(source)) as container:
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    for index, frame in enumerate(container.decode(stream)):
        assert frame.width % 32 == 0, "fixture needs a separate native-alignment reference"
        fmt = "rgb24" if frame.format.name in ("yuvj420p", "yuvj422p", "yuvj444p", "rgb24", "rgba", "pal8") else "gbrpf32le"
        direct = torch.from_numpy(frame.to_ndarray(format=fmt))
        if fmt == "rgb24":
            direct = direct.float() / 255
        diff = float((images[index] - direct).abs().max())
        max_diff = max(max_diff, diff)
        assert torch.equal(images[index], direct), (index, diff)
        count += 1
out_dir = root / "runtime_deps/compat_test"
out_dir.mkdir(exist_ok=True)
dest = out_dir / "walk_native_h264_sdr.mp4"
video = CreateVideo.execute(images=images, fps=24.0, bit_depth=8, color_space="sRGB")[0]
video.save_to(str(dest), format="mp4", codec="h264", crf=16, preset="ultrafast")
with av.open(str(dest)) as container:
    stream = container.streams.video[0]
    metadata = {"fps": str(stream.average_rate), "declared_frames": stream.frames,
                "primaries": stream.codec_context.color_primaries,
                "transfer": stream.codec_context.color_trc,
                "colorspace": stream.codec_context.colorspace,
                "range": stream.codec_context.color_range,
                "pixel_format": stream.format.name}
    output_frames = sum(1 for _ in container.decode(stream))
assert output_frames == 107
assert metadata == {"fps": "24", "declared_frames": 107, "primaries": 1,
                    "transfer": 13, "colorspace": 1, "range": 1, "pixel_format": "yuv420p"}, metadata
try:
    VideoFromComponents(components, bit_depth=10, color_space="HDR PQ")
except ValueError:
    hdr_rejected = True
else:
    raise AssertionError("HDR was not rejected")
report = {"pyav": av.__version__, "torch": torch.__version__, "decoded_frames": count,
          "source_shape": list(images.shape), "max_abs_difference_native_vs_direct": max_diff,
          "output_frames": output_frames, "codec_metadata": metadata,
          "hdr_rejected": hdr_rejected, "output_path": str(dest),
          "gpu_used": False}
(out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
