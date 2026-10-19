"""Read-only imports of the sealed v1 kernel and original31 generator."""
import importlib.util
from pathlib import Path

V1_ROOT=Path(__file__).resolve().parent.parent/'phase_shape_profile_candidate_v1'
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
V1=load(V1_ROOT/'profile.py','sealed_v1_kernel')
SYNTH=load(V1_ROOT/'synthetic.py','sealed_v1_synthetic')
