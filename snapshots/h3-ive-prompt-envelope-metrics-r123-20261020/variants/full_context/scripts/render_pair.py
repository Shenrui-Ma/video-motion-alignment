"""Reuse the SHA-bound R123 consumer in this variant namespace."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/render_pair.py')
_shared_bytes=_shared.read_bytes()
assert _hashlib.sha256(_shared_bytes).hexdigest()=='22837fc3db5ecd9e0a2019279cfc7184a2790b31743e93b0aff7d6eb85b11c8a'
_display_code=_shared_bytes.decode().replace('R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。','提示词采用H3完整Context-IR结构，保留benchmark的源描述、编辑原句和目标描述，并标明被编辑主体。')
exec(compile(_display_code,str(_shared),'exec'),globals())
