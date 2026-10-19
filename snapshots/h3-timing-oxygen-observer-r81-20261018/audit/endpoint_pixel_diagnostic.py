"""Descriptive full-prefix RGB difference; not a pure host/kernel equivalence test."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
a=ROOT.parent/'h3-ivebench-expanded-metrics-r73-20261018/incoming/short_0252/native.mp4'
b=ROOT/'outputs/attempt1/step019.mp4'
gate=json.loads((ROOT/'configs/PAIR_RUNTIME_GATE.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(a)==gate['runs']['native']['video']['sha256']
cmd=lambda p:['ffmpeg','-v','error','-threads','2','-i',str(p),'-map','0:v:0','-fps_mode','passthrough','-pix_fmt','rgb24','-threads','2','-f','rawvideo','-']
procs=[subprocess.Popen(cmd(p),stdout=subprocess.PIPE,stderr=subprocess.PIPE) for p in (a,b)]
frame_bytes=1312*736*3;rows=[]
try:
    for i in range(107):
        raw=[p.stdout.read(frame_bytes) for p in procs];assert all(len(r)==frame_bytes for r in raw)
        x,y=[np.frombuffer(r,dtype=np.uint8).astype(np.int16) for r in raw];d=np.abs(x-y)
        rows.append({'frame':i,'valid_prefix':i<98,'RGB_MAE_0_255':float(d.mean()),'RGB_max_abs':int(d.max()),'identical_channel_fraction':float((d==0).mean())})
    for p in procs:
        assert p.stdout.read(1)==b''
        assert p.wait(timeout=30)==0,p.stderr.read().decode()
finally:
    for p in procs:
        if p.poll() is None:p.terminate();p.wait(timeout=10)
record={'schema':'r81-endpoint-description-v1','original_native':{'file':str(a),'sha256':sha(a)},'x0_step019_decoded':{'file':str(b),'sha256':sha(b)},'valid_prefix_frames':98,'all_frames':107,'same_frame_order_no_warp':True,'mean_RGB_MAE_0_255_valid':sum(r['RGB_MAE_0_255'] for r in rows[:98])/98,'max_RGB_abs_valid':max(r['RGB_max_abs'] for r in rows[:98]),'mean_identical_channels_valid':sum(r['identical_channel_fraction'] for r in rows[:98])/98,'frames':rows,'interpretation':'Compound endpoint boundary: x0_step019 vs final_sampler FP32 residual, host9/host41 VAE runtime, and video encoding can differ. This does not isolate a host/kernel cause or define a motion metric.'}
(ROOT/'audit/consumer_attempt1/ENDPOINT_PIXEL_DESCRIPTION.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('frames','original_native','x0_step019_decoded')}))
