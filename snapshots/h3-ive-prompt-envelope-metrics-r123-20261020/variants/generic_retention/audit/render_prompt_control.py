"""Bind the existing prompt comparison renderer to the retention variant."""
import hashlib as _hashlib
from pathlib import Path as _Path
_shared=_Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/audit/render_prompt_control.py')
_bytes=_shared.read_bytes()
assert _hashlib.sha256(_bytes).hexdigest()=='b003e7d63fac58ed8c7fad97c7967f8b79331dd97ce697a9e6f963b856548f20'
_code=_bytes.decode()
assert _code.count("previous=ROOT.parent/'h3-ive-official-positive-recheck-metrics-r121-20261020'")==1
_code=_code.replace("previous=ROOT.parent/'h3-ive-official-positive-recheck-metrics-r121-20261020'","previous=Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020')")
assert _code.count("assert bare['5']['inputs']['prompt']==p['original_task']['edit_prompt']")==1
_code=_code.replace("assert bare['5']['inputs']['prompt']==p['original_task']['edit_prompt']","assert bare['5']['inputs']['prompt']==TASK_ENVELOPE+p['original_task']['edit_prompt']")
assert _code.count("('1.参考视频','2.官方原句','3.任务格式 + 官方原句')")==1
_code=_code.replace("('1.参考视频','2.官方原句','3.任务格式 + 官方原句')","('1.参考视频','2.任务格式','3.任务格式 + 通用保留要求')")
assert _code.count('source_bare_envelope_full105.mp4')==1
_code=_code.replace('source_bare_envelope_full105.mp4','source_envelope_retention_full105.mp4')
assert _code.count("['source','r121_bare_native','r123_envelope_native']")==1
_code=_code.replace("['source','r121_bare_native','r123_envelope_native']","['source','r123_envelope_native','r123_generic_retention_native']")
assert _code.count('饮酒加眼镜：提示词格式对照')==1
_code=_code.replace('饮酒加眼镜：提示词格式对照','饮酒加眼镜：通用保留要求对照')
assert _code.count('H3_R123_饮酒提示词格式对照_20261020.html')==1
_code=_code.replace('H3_R123_饮酒提示词格式对照_20261020.html','H3_R123_饮酒通用保留要求对照_20261020.html')
assert _code.count('比较任务格式标识对编辑结果的影响')==1
_code=_code.replace('比较任务格式标识对编辑结果的影响','比较通用保留要求对编辑结果的影响')
exec(compile(_code,str(_shared),"exec"),globals())
