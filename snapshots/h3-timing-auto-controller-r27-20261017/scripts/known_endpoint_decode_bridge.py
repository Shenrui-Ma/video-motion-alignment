"""Bridge-only launcher for the exact live decoder on an idle GPU, no DiT.

Only resource admission is replaced: the bridge has no resident DiT parent.
The production decoder, request validation, lifetime guard, VAE, OOM rejection,
normalization and RGB writer execute unchanged. This does not certify residency.
"""
import sys
import decode_live_child as live
from observer_import import t

def idle_bridge_admission(parent,uuid):
    t.require(t.alive(parent),'bridge parent disappeared')
    t.require(uuid==t.DECODER_UUID,'bridge GPU differs')
    return dict(live.assert_idle_gpu(uuid),scope='standalone known-endpoint bridge; no DiT residency claim')

if __name__=='__main__':
    live.t.co_resident_admission=idle_bridge_admission
    raise SystemExit(live.main(sys.argv[1:]))
