"""CPU-only DWPose comparison of actual prepared RGB and VAE reconstruction."""
import argparse,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from common import *

def main():
    a=argparse.ArgumentParser();a.add_argument('--inputs',type=Path,required=True);a.add_argument('--decoded',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    root=Path(__file__).resolve().parents[1];p=json.loads((args.inputs/'PREPARED.json').read_text());d=json.loads((args.decoded/'RESULT.json').read_text());protocol=json.loads((root/'configs/pose_protocol.json').read_text())
    require(p['status']=='complete' and d['status']=='complete','completed source/decode')
    require(d['prepared_sha256']==sha(args.inputs/'PREPARED.json') and d['fallback_guard']['calls']==0,'decode input/fallback binding')
    require(p['contract_sha256']==d['contract_sha256']==sha(root/'configs/contract.json'),'contract unchanged')
    for rel,digest in json.loads((root/'configs/physical_code.json').read_text()).items():require(sha(root/rel)==digest,'physical code unchanged')
    for path,digest in protocol['frozen_external'].items():require(sha(path)==digest,'pose dependency unchanged '+path)
    require(not args.output.exists(),'new evaluation output');args.output.mkdir(parents=True)
    pose_script=next(k for k in protocol['frozen_external'] if k.endswith('/pose_probe.py'))
    videos={'prepared':(args.inputs,p['products']['prepared_158']),'reconstruction':(args.decoded,d['products']['reconstruction_158'])};poses={};receipts={}
    for name,(folder,item) in videos.items():
        video=folder/item['file'];require(sha(video)==item['sha256'],'video identity '+name)
        dest=args.output/name;dest.mkdir();cmd=[sys.executable,pose_script,'--video',str(video),'--output-dir',str(dest),'--threads','4','--stride','1'];start=time.monotonic()
        with (dest/'pose.log').open('x') as log:
            done=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4'),timeout=240)
        require(done.returncode==0,'pose failure; log retained '+name)
        path=dest/(video.stem+'.pose.json');raw=json.loads(path.read_text());require(raw['video']['sha256']==item['sha256'] and len(raw['frames'])==158,'actual pose identity/count')
        poses[name]=raw;receipts[name]={'file':str(path),'sha256':sha(path),'video_sha256':sha(video),'seconds':time.monotonic()-start,'command':cmd}
    require(poses['prepared']['provenance']==poses['reconstruction']['provenance'],'pose runtime same')
    sys.path.insert(0,str(root/'runtime/physical'));import evaluate
    report={'status':'complete','scope':'reference VAE roundtrip only; source runtime .41 encode plus .9 decode','prepared_receipt_sha256':sha(args.inputs/'PREPARED.json'),'decode_receipt_sha256':sha(args.decoded/'RESULT.json'),'poses':receipts,'physical_time_step_ms':125,'confidence_results':{}}
    for threshold in (.3,.5):
        source=evaluate.original_time_view(poses['prepared'],threshold);edited=evaluate.original_time_view(poses['reconstruction'],threshold)
        report['confidence_results'][str(threshold)]=[evaluate.diagnostic(source,edited,w,f) for w in evaluate.PROTOCOL['windows_inclusive'] for f in evaluate.FEATURES]
    write(args.output/'PHYSICAL.json',evaluate.metrics.clean(report));print(args.output/'PHYSICAL.json')
if __name__=='__main__':main()
