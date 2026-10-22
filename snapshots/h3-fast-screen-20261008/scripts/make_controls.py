"""CPU-only reference preprocessing; retains the original canvas and subject scale."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

RUN = Path('/data5/researcher/h3_runs/fast_screen_controls_20261008')
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_MODULES_CACHE'] = str(RUN / 'temp/hf_modules')

import numpy as np
from PIL import Image
import torch
from torchvision import transforms
from safetensors.torch import load_file
from transformers.dynamic_module_utils import get_class_from_dynamic_module


def main():
    torch.set_num_threads(4)
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=["firefly_notsin107", "coast_bluestudio90"])
    args = parser.parse_args()
    start = time.time()
    model_path = Path('/data5/researcher/ComfyUI/models/RMBG/RMBG-2.0')
    model_class = get_class_from_dynamic_module(
        'birefnet.BiRefNet', str(model_path), local_files_only=True,
    )
    model = model_class(bb_pretrained=False)
    model.load_state_dict(load_file(str(model_path / 'model.safetensors')), strict=True)
    model = model.eval().to('cpu')
    original = Image.open(RUN / 'input' / (args.name + '_original.png')).convert('RGB')
    transform = transforms.Compose([
        transforms.Resize((1024, 1024)), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    with torch.inference_mode():
        prediction = model(transform(original).unsqueeze(0))[-1].sigmoid().cpu()[0, 0]
    alpha = Image.fromarray((prediction.numpy() * 255).clip(0, 255).astype('uint8'))
    alpha = alpha.resize(original.size, Image.Resampling.LANCZOS)
    alpha.save(RUN / 'input' / (args.name + '_alpha.png'))
    outputs = {}
    for label, color in [('neutral', (127, 127, 127))]:
        composite = Image.composite(original, Image.new('RGB', original.size, color), alpha)
        path = RUN / 'input' / (args.name + '_' + label + '.png')
        composite.save(path)
        outputs[label] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    arr = np.asarray(alpha, dtype=np.float32) / 255
    info = {'method': 'existing RMBG-2.0, CPU, no retraining',
            'original_size': original.size, 'segmentation_size': [1024, 1024],
            'foreground_fraction_alpha_gt_half': float((arr > 0.5).mean()),
            'same_canvas_and_subject_coordinates': True,
            'elapsed_seconds': time.time() - start, 'outputs': outputs,
            'cuda_initialized': torch.cuda.is_initialized(),
            'pid': os.getpid(),
            'confound': 'Preprocessing changes Qwen/VAE content; not a proof of attention causality.'}
    (RUN / 'configs' / (args.name + '_controls.json')).write_text(json.dumps(info, indent=2))
    print(json.dumps(info))


if __name__ == '__main__':
    main()
