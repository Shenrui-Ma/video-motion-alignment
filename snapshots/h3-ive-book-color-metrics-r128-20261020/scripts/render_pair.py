"""Reuse the verified R120 consumer in the R128 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/render_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='cb0a0649dad3a27bac5d3d946a54915fb9864de2e33d6b72b02218f606803d95'
_code=_shared_bytes.decode().replace('r120','r128').replace('R120','R128')
_code=_code.replace('R128固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。','R128将蓝色书封面改为红色，使用完整2.68秒原片，只输入参考视频。提示词用完整Context-IR组织官方原始描述、编辑要求和目标描述。')
assert _code.count("'fixed_source_denominator':3")==1
_code=_code.replace("'fixed_source_denominator':3","'fixed_source_denominator':config()['fixed_source_denominator']")
exec(compile(_code,str(_shared),'exec'),globals())
