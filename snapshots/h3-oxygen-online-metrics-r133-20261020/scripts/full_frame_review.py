from pathlib import Path as _P
import hashlib as _H
_p=_P('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/full_frame_review.py');_b=_p.read_bytes();assert _H.sha256(_b).hexdigest()=='205c40f1d10a1227e3664f917c3ef6ed500c64cbc07c6792509ccb87d2d99fbf'
_s=_b.decode().replace("'3.时序引导'","'3.自动时序引导'")
_s=_s.replace('len(inputs) in (2, 3)','len(inputs) in (3, 4)').replace("labels = ('1.参考视频', '2.普通编辑', '3.自动时序引导')[:len(inputs)]","labels = ('1.参考视频', '2.普通编辑', '3.固定时序引导', '4.自动时序引导') if len(inputs)==4 else ('1.参考视频', '2.普通编辑', '3.自动时序引导')")
exec(compile(_s,str(_p),'exec'),globals())
