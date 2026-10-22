"""Reuse SHA-bound R120 consumer helpers for one R122 source."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/render_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='358ac4ac518fd2cbff92d11a1b7310ab4310125b3cf80b70a87a99b8f4d71438'
_code=_shared_bytes.decode().replace('r120','r122').replace('R120','R122')
assert _code.count('R122固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。')==1
_code=_code.replace('R122固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。','R122将原参考视频中的书改为蓝色，使用原片前4.4秒，只输入参考视频。实际提示词包含官方编辑原句、任务格式标识与通用保留要求。')
exec(compile(_code,str(_shared),'exec'),globals())
