"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/render_native.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '6701f554d200e886317f590d6df5804995ebd89b3d33277638e8e4b8650417be'
_text = _data.decode()
assert _text.count('R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。') == 1
_text = _text.replace('R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。', 'R141复核老人替换任务。使用官方编辑原句、参考视频绑定和通用保留要求；同源 seed1703，不增加独立来源。').replace("R123", "R141")
exec(compile(_text, str(_shared), "exec"), globals())
