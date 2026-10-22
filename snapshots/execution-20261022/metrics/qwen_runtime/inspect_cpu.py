"""CPU metadata verification, never constructs or loads model weights."""
import importlib.metadata as metadata
import json
import os
import subprocess
import time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch
from transformers import AutoConfig, AutoProcessor, Qwen2_5_VLForConditionalGeneration
from awq.modules.linear import gemm
from batch_eval import ROOT, REVISION, MODEL_ID, official_modules, atomic
model = ROOT.parent / 'weights/Qwen2.5-VL-72B-Instruct-AWQ'
config = AutoConfig.from_pretrained(str(model), local_files_only=True)
processor = AutoProcessor.from_pretrained(str(model), local_files_only=True)
modules = official_modules()
status = json.loads((ROOT / 'download_status.snapshot.json').read_text())
assert status['complete'] is True and status['revision'] == REVISION
for name, row in status['files'].items():
    assert (model / name).stat().st_size == row['bytes'], name
assert torch.cuda.is_initialized() is False
atomic(ROOT / 'CPU_VERIFICATION.json', {
    'time_unix': time.time(), 'status': 'cpu_preparation_verified_gpu_pending',
    'model_id': MODEL_ID, 'revision': REVISION, 'weight_loading_performed': False,
    'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'], 'cuda_initialized': torch.cuda.is_initialized(),
    'config_class': type(config).__name__, 'processor_class': type(processor).__name__,
    'quantization_config': config.quantization_config, 'config_torch_dtype': str(config.torch_dtype),
    'download_snapshot_complete': status['complete'], 'all_checkpoint_file_sizes_match': True,
    'awq_triton_available': gemm.TRITON_AVAILABLE, 'awq_compiled_extension_available': gemm.awq_ext is not None,
    'packages': {name: metadata.version(name) for name in ['torch', 'torchvision', 'triton', 'transformers', 'autoawq', 'accelerate', 'qwen-vl-utils', 'av', 'decord']},
    'torch_path': torch.__file__, 'processor_path': str(model),
    'official_modules_imported': list(modules),
    'pip_check': (ROOT / 'pip_check.txt').read_text().strip(),
    'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
    'network': 'Aliyun PyPI direct; all proxy variables unset; NO_PROXY=*; HTTP 200 captured',
    'gpu_work_remaining': ['two physically distinct GPUs with zero existing compute processes',
                           'AWQ Triton CUDA kernel smoke test', 'full 72B model loading and real IS/CF generation'],
})
print((ROOT / 'CPU_VERIFICATION.json').read_text())
