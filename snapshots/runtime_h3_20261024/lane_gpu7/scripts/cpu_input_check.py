"""Validate input with actual Comfy folder_paths before creating any CUDA service."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(sys.argv[1]).resolve()
CORE=Path('/data3/research-user/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI')
# comfy.cli_args only reads Comfy options when enabled. Strip this checker argv.
sys.argv=[sys.argv[0]]
sys.path.insert(0,str(CORE))
import folder_paths
folder_paths.set_input_directory(str(ROOT/'input'))
p=ROOT/'input/short_0177_video.mp4'
assert p.is_file() and not p.is_symlink(), 'Require lane-local real input file'
assert folder_paths.exists_annotated_filepath(p.name), 'Actual Comfy input boundary validation rejected file'
assert Path(folder_paths.get_annotated_filepath(p.name)).resolve()==p.resolve()
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d5da95935608029e1c458def4cb1c09a3ce42ea7e6d60cc9a44c9c6575f801f2'
print(json.dumps({'passed':True,'input':str(p),'input_bytes':p.stat().st_size,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'folder_paths_module':folder_paths.__file__,'folder_paths_source_sha256':hashlib.sha256(Path(folder_paths.__file__).read_bytes()).hexdigest(),'cuda_module_imported':'torch.cuda' in sys.modules}))
