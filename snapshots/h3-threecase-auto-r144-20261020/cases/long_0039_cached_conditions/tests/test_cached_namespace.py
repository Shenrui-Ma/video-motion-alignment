"""Reproduce Comfy's absolute-path module namespace in a clean interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class CachedNamespace(unittest.TestCase):
    def test_original_signature_without_extensions_search_path(self):
        package = Path(__file__).resolve().parents[1] / "extensions/H3CachedCondition"
        code = """
import hashlib,importlib.util,sys
from pathlib import Path
import torch
package=Path(sys.argv[1])
assert str(package.parent) not in sys.path
name=str(package).replace('.','_x_')
spec=importlib.util.spec_from_file_location(name,package/'__init__.py')
module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
for dtype in (torch.float32,torch.bfloat16,torch.int64):
 value=torch.arange(12).to(dtype).reshape(3,4)
 expected={'shape':[3,4],'dtype':str(dtype),'sha256':hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}
 assert module.signature(value)==expected
assert 'H3X0Readout' not in sys.modules
assert not torch.cuda.is_initialized()
"""
        subprocess.run([sys.executable, "-I", "-c", code, str(package)], check=True,
                       capture_output=True, text=True, timeout=45)


if __name__ == "__main__":
    unittest.main()
