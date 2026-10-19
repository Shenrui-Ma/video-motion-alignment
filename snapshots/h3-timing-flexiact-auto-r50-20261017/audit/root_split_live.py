"""Root administration for R50's dedicated decoder gate and launch checks."""
import argparse,hashlib,json,os,runpy,subprocess,sys,time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
S=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
MAIN='GPU-REDACTED'
DECODER='GPU-REDACTED'
MANIFEST='13d2842849143f4d30122e51a8dd1ab05e3b083f9f1af7de8777f4ec35798b93'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def ident(pid):
    p=Path('/proc')/str(pid)
    return {'pid':int(pid),'uid':p.stat().st_uid,'start_ticks':int(p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]),'cmdline_sha256':sha(p/'cmdline')}
def write_new(p,data):
    with Path(p).open('x') as f:f.write(json.dumps(data,indent=2)+'\n')
def check(decoder_only=False):
    assert sha(R/'deploy_manifest.json')==MANIFEST
    for rel,row in read(R/'deploy_manifest.json')['files'].items():assert sha(R/rel)==row['sha256'],rel
    clean=read(S/'processes/cleanup.json')
    assert clean['pid']==63582 and all(clean.get(k) is True for k in ['process_absent','own_compute_absent','child_compute_absent'])
    assert clean['service_record']['identity']['start_ticks']=='2625625538'
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
    for line in raw.splitlines():
        gpu,pid=[x.strip() for x in line.split(',')]
        targets=(DECODER,) if decoder_only else (MAIN,DECODER)
        assert gpu not in targets,'target card occupied'
        try:uid=(Path('/proc')/pid).stat().st_uid
        except FileNotFoundError:continue
        assert uid!=os.getuid(),'unexpected own compute'
    return {'compute_rows':raw,'r53_cleanup_sha256':sha(S/'processes/cleanup.json')}
def main(phase):
    os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',TMPDIR=str(R/'temp'),TMP=str(R/'temp'),TEMP=str(R/'temp'),PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0]=[str(R/'scripts'),'/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps']
    before=check(decoder_only=phase in ('decoder','go'))
    if phase=='decoder':
        out=R/'audit/known_endpoint_158_split_gate.json';assert not out.exists()
        write_new(R/'audit/root_split_decoder_parent.json',{'identity':ident(os.getpid()),'preflight':before,'time':time.time()})
        target=R/'scripts/known_endpoint_158_gate.py';sys.argv=[str(target),'--root-admitted','--output',str(out)]
        runpy.run_path(str(target),run_name='__main__')
    elif phase=='go':
        d=R/'audit/observations/known_endpoint_158_split_v2';ready=read(d/'decoder_ready.json');identity=ready['identity']
        assert ident(identity['pid'])==identity and identity['uid']==os.getuid()==1016
        assert ready['gpu_uuid']==DECODER
        command=(Path('/proc')/str(identity['pid'])/'cmdline').read_bytes()
        assert str(R/'scripts/known_endpoint_decode_bridge.py').encode() in command
        write_new(d/'decoder_go.json',{'root_approved':True,'identity':identity,'gpu_uuid':DECODER})
        print(json.dumps({'decoder_approved':identity,'preflight':before}))
    elif phase=='resource':
        target=R/'audit/build_split_resource_admission_proposed.py'
        assert sha(target)=='c30970b05b0a4f91089cf228cc83ab58f192c75133f6245893d1304f4bc57a94'
        sys.argv=[str(target),'--root-approved'];runpy.run_path(str(target),run_name='__main__')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['decoder','go','resource']);main(p.parse_args().phase)
