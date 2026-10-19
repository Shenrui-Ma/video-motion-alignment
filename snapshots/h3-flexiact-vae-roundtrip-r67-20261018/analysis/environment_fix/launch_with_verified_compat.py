"""Administrative import repair around the unchanged frozen R67 decoder."""
import hashlib,importlib.util,json,os,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BOOT=Path('/data5/researcher/h3_runs/timing_ivebench_forced_r63_20261018/scripts/compatibility_bootstrap.py')
BOOT_SHA='0d4152378feae0ae4b639587fe67c2c8eb74086e80aee6f5e4ea476329c7fe89'
DECODER_SHA='570a2858403aeb0d5bc201ea2caa85cfd0adef5bfbe2f2579d927b6b9d22ae7e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert sha(BOOT)==BOOT_SHA,'existing bootstrap source changed'
    decoder=ROOT/'scripts/decode_reference.py';assert sha(decoder)==DECODER_SHA,'frozen decoder changed'
    spec=importlib.util.spec_from_file_location('compatibility_bootstrap',BOOT);module=importlib.util.module_from_spec(spec);sys.modules['compatibility_bootstrap']=module;spec.loader.exec_module(module)
    assert callable(module.install) and callable(module.install_video_compat)
    if sys.argv[1:]==['--cpu-import-check']:
        os.environ['CUDA_VISIBLE_DEVICES']=''
        c=json.loads((ROOT/'configs/contract.json').read_text())
        sys.path.insert(0,c['dependencies']);sys.path.insert(0,c['core']);sys.path.insert(0,str(ROOT/'scripts'))
        import torch
        assert not torch.cuda.is_initialized()
        module.install();module.install_video_compat()
        import comfy.cli_args
        comfy.cli_args.args.cpu=True
        comfy.cli_args.args.disable_dynamic_vram=True
        comfy.cli_args.args.disable_cuda_malloc=True
        comfy.cli_args.args.use_pytorch_cross_attention=True
        import comfy.sd,comfy.utils,comfy.model_management
        import decode_reference
        guard=decode_reference.install_fallback_guard(comfy.sd.VAE)
        assert comfy.model_management.get_torch_device().type=='cpu' and not torch.cuda.is_initialized()
        assert hasattr(comfy.ldm.minimax.vae,'MiniMaxH3VideoVAE')
        print(json.dumps({'status':'CPU_FULL_IMPORT_PASS','bootstrap':str(BOOT),'bootstrap_sha256':BOOT_SHA,'decoder_sha256':DECODER_SHA,'torch':torch.__version__,'cuda_initialized':torch.cuda.is_initialized(),'comfy_sd':comfy.sd.__file__,'vae_class':str(comfy.ldm.minimax.vae.MiniMaxH3VideoVAE),'fallback_guard':guard}));return
    sys.path.insert(0,str(ROOT/'scripts'))
    sys.argv=[str(decoder),*sys.argv[1:]]
    runpy.run_path(str(decoder),run_name='__main__')
if __name__=='__main__':main()
