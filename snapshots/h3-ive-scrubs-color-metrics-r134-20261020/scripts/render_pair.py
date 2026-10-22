"""Reuse the verified R120 consumer in the R134 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/render_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='cb0a0649dad3a27bac5d3d946a54915fb9864de2e33d6b72b02218f606803d95'
_code=_shared_bytes.decode().replace('r120','r134').replace('R120','R134')
_code=_code.replace('R134固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。','R134将蓝色手术服改为绿色，使用完整原片，只输入参考视频。提示词保留官方编辑原句，并加入参考视频绑定与通用保留要求。')
assert _code.count("'fixed_source_denominator':3")==1
_code=_code.replace("'fixed_source_denominator':3","'fixed_source_denominator':config()['fixed_source_denominator']")
exec(compile(_code,str(_shared),'exec'),globals())
