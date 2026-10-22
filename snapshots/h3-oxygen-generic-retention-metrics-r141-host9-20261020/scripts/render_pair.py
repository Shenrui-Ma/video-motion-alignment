"""Load the existing, hash-bound consumer helper for R141."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared = _Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/render_pair.py')
_data = _shared.read_bytes()
assert _hashlib.sha256(_data).hexdigest() == '22837fc3db5ecd9e0a2019279cfc7184a2790b31743e93b0aff7d6eb85b11c8a'
_text = _data.decode()
assert _text.count('R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。') == 1
_text = _text.replace('R123复核饮酒男子加眼镜。提示词保留官方 edit_prompt 原句，前面加入任务类型与参考视频标识。', 'R141复核老人替换任务。使用官方编辑原句、参考视频绑定和通用保留要求；同源 seed1703，不增加独立来源。').replace("R123", "R141")
exec(compile(_text, str(_shared), "exec"), globals())
