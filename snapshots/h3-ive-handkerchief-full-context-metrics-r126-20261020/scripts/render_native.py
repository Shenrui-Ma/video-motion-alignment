"""Reuse the verified R120 consumer in the R126 namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-official-prompt-metrics-r120-20261019/scripts/render_native.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='358ac4ac518fd2cbff92d11a1b7310ab4310125b3cf80b70a87a99b8f4d71438'
_code=_shared_bytes.decode().replace('r120','r126').replace('R120','R126')
_code=_code.replace('R126固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。','R126在男子手中添加白手帕，使用原片7–13秒，只输入参考视频。提示词用完整Context-IR组织官方原始描述、编辑要求和目标描述。')
assert _code.count("'fixed_source_denominator':3")==1
_code=_code.replace("'fixed_source_denominator':3","'fixed_source_denominator':config()['fixed_source_denominator']")
exec(compile(_code,str(_shared),'exec'),globals())
