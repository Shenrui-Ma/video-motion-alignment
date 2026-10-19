"""Bridge-only launcher for the exact live decoder on an idle GPU, no DiT.

Only resource admission is replaced: the bridge has no resident DiT parent.
The production decoder, request validation, lifetime guard, VAE, OOM rejection,
normalization and RGB writer execute unchanged. This does not certify residency.
"""
import sys,os,time,json
from pathlib import Path
import decode_live_child as live
from observer_import import t

def idle_bridge_admission(parent,uuid):
    t.require(t.alive(parent),'bridge parent disappeared')
    t.require(uuid==t.DECODER_UUID,'bridge GPU differs')
    return dict(live.assert_idle_gpu(uuid),scope='standalone known-endpoint bridge; no DiT residency claim')

if __name__=='__main__':
    # CUDA starts only after root records this exact temporary decoder beside
    # any admitted peer service. This gate applies only to this standalone test.
    parent=json.loads(sys.argv[sys.argv.index('--parent-json')+1])
    t.install_lifetime_guard(parent)
    directory=Path(os.environ['R55_DECODER_APPROVAL_DIRECTORY'])
    t.require(directory.parent==t.ROOT/'audit/observations','approval outside owned observations')
    own=t.identity(os.getpid());t.require(own is not None,'cannot bind decoder identity')
    ready=directory/'decoder_ready.json';go=directory/'decoder_go.json'
    t.write_new(ready,{'schema':'r55-standalone-decoder-preCUDA-v1','identity':own,'gpu_uuid':t.DECODER_UUID})
    deadline=time.monotonic()+600
    while not go.exists():
        if time.monotonic()>deadline:raise TimeoutError('root decoder admission pending after600s')
        time.sleep(.25)
    approval=t.read_json(go)
    t.require(approval.get('root_approved') is True and approval.get('identity')==own and approval.get('gpu_uuid')==t.DECODER_UUID,'wrong standalone decoder root approval')
    live.t.separate_decoder_admission=idle_bridge_admission
    raise SystemExit(live.main(sys.argv[1:]))
