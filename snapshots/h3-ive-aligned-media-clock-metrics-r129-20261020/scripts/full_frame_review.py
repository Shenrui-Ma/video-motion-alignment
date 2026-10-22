from pathlib import Path as _P
import hashlib as _H
_p=_P('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/full_frame_review.py');_b=_p.read_bytes();assert _H.sha256(_b).hexdigest()=='205c40f1d10a1227e3664f917c3ef6ed500c64cbc07c6792509ccb87d2d99fbf'
_s=_b.decode().replace("'3.时序引导'","'3.RoPE原点对齐'")
exec(compile(_s,str(_p),'exec'),globals())
