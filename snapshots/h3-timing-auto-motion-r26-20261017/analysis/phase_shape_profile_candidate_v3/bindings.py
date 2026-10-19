"""Load immutable v2 code; keep the candidate generator/evaluation byte-identical."""
import importlib.util
import sys
from pathlib import Path
V2_ROOT=Path(__file__).resolve().parent.parent/'phase_shape_profile_candidate_v2'
sys.path.append(str(V2_ROOT))
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
V2=load(V2_ROOT/'profile_v2.py','sealed_v2_baseline')
