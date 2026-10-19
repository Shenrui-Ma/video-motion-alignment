"""Root-only 0-DiT Flash gate. Same PID waits before first CUDA initialization."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from r46_contract import ROOT,read,sha,identity_schema,require


def precuda(control,timeout=1800):
    import service
    control=Path(control);control.mkdir(parents=True,exist_ok=True)
    ready=control/'ready.json';go=control/'go.json'
    require(not ready.exists() and not go.exists(),'preserve prior gate evidence; use new control directory')
    identity=service.external_identity(os.getpid());identity_schema(identity,external=True)
    record={'pid':os.getpid(),'identity':identity,'script_sha256':sha(__file__),
            'protocol_sha256':sha(ROOT/'configs/SCIENCE_PROTOCOL.json'),'gpu_uuid':service.GPU,'CUDA_initialized':False}
    ready.write_text(json.dumps(record,indent=2)+'\n')
    started=time.monotonic()
    while not go.exists():
        if time.monotonic()-started>timeout:raise TimeoutError('root preCUDA gate not released')
        time.sleep(.25)
    require(read(go)==record and service.external_identity(os.getpid())==identity,'root gate/identity changed')
    service.gpu_readiness()
    admission=read(ROOT/'configs/admission.json')
    service.check_admission(admission,service.compute_processes(),{'queue_running':[],'queue_pending':[]})
    return record


def main():
    p=argparse.ArgumentParser();p.add_argument('--control-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    owner=precuda(a.control_dir)
    import torch
    sys.path.insert(0,str(ROOT/'extensions'))
    from H3AttentionStateProbe.probe import read_distribution
    from H3AttentionStateProbe.dependencies import router
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==owner['gpu_uuid'],'exact UUID CUDA visibility required')
    require(not torch.cuda.is_initialized(),'CUDA initialized before gate')
    device=torch.device('cuda:0');torch.set_num_threads(1)
    # Deterministic analytic input, no global random sampling.
    q=(torch.arange(4*1050*128,device=device,dtype=torch.float32).reshape(1,4,1050,128)%251/251-.5).to(torch.bfloat16)
    k=(torch.arange(4*39606*128,device=device,dtype=torch.float32).reshape(1,4,39606,128)%257/257-.5).to(torch.bfloat16)
    v=(k.float()*3).cos().to(torch.bfloat16)
    before=[x.clone() for x in (q,k,v)]
    cpu_rng=torch.random.get_rng_state().clone();cuda_rng=torch.cuda.get_rng_state().clone()
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();started=time.perf_counter()
    # Fixture has only R keys; known reference mass=1. Actual joint mass is tested at first production probe.
    _,full_lse=router.flash_attention_lse(q,k,v)
    result=read_distribution(q,k,v,full_lse,router.flash_attention_lse,query_bins=[t for t in range(42) for _ in range(25)])
    torch.cuda.synchronize();elapsed=time.perf_counter()-started
    require(result['quality']['status']=='PASS','actual subset-geometry Flash grouping failed')
    require(all(torch.equal(x,y) for x,y in zip((q,k,v),before)) and torch.equal(cpu_rng,torch.random.get_rng_state()) and
            torch.equal(cuda_rng,torch.cuda.get_rng_state()),'GPU fixture inputs/RNG changed')
    sq,sk,sv=q[:,:,:7,:],k[:,:,:19,:],v[:,:,:19,:]
    _,small_lse=router.flash_attention_lse(sq,sk,sv)
    dense_lse=torch.logsumexp(sq.double()@sk.double().transpose(-1,-2)/(128**.5),-1)
    err=float((small_lse.double()-dense_lse).abs().max())
    require(err<=0.005,'BF16 fixed dense LSE oracle tolerance exceeded')
    record={'passed':True,'DiT_NFE':0,'Euler_updates':0,'Qwen_VAE_calls':0,'owner':owner,
            'protocol_sha256':sha(ROOT/'configs/SCIENCE_PROTOCOL.json'),'script_sha256':sha(__file__),
            'probe_sha256':sha(ROOT/'extensions/H3AttentionStateProbe/probe.py'),'quality':result['quality'],
            'small_BF16_dense_lse_max_abs':err,'query_shape':list(q.shape),'reference_shape':list(k.shape),
            'seconds':elapsed,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'inputs_RNG_exact':True,'limitations':'model-free selected geometry; does not establish actual full-model endpoint or loaded-model coexistence'}
    a.output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
