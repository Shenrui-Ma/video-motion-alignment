from pathlib import Path
import json,hashlib,time
D=Path('/Users/researcher/DevProjects');O=D/'h3-ive-basketball-shortprompt-metrics-r109-20261019';R=D/'h3-ive-basketball-boundprompt-metrics-r110-20261019';P=D/'h3-timing-ive-basketball-boundprompt-r110-20261019'
assert not R.exists();R.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((O/'CONSUMER_FREEZE.json').read_text())
for rel,digest in freeze['files'].items():
 src=O/rel;assert sha(src)==digest;dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 s=src.read_text().replace('r109','r110').replace('R109','R110').replace('basketball-shortprompt','basketball-boundprompt').replace('basketball_shortprompt','basketball_boundprompt').replace('root_shortprompt_attempt1','root_boundprompt_attempt1')
 if rel=='scripts/consume.py':
  s=s.replace("ROOT.parent/'h3-ive-task-repair-metrics-r100-20261019/incoming_pairs/short_0114/native.mp4'","ROOT.parent/'h3-ive-basketball-shortprompt-metrics-r109-20261019/incoming/plain.mp4'")
  s=s.replace('464544e0c13a67fcc9c461055215c5da8572a0b4e7b15b0404c3b462aec7a70b',sha(O/'incoming/plain.mp4'))
  s=s.replace('六段提示词与简短提示词','简短提示词与显式参考提示词').replace('2.六段提示词普通编辑','2.一句话普通编辑').replace('3.简短提示词普通编辑','3.显式参考普通编辑')
  s=s.replace('actual R100 P1 ordinary, R110 exact-short-prompt ordinary','actual R109 short ordinary, R110 reference-bound ordinary')
  s=s.replace('actual R100 ordinary video','actual R109 ordinary video').replace('SIX-SECTION P1','SHORT PROMPT').replace('EXACT SHORT PROMPT','REFERENCE-BOUND PROMPT')
  s=s.replace('篮球替换：六段提示词与一句话提示词','篮球替换：一句话提示词与明确绑定原视频的提示词').replace('中：原六段提示词普通编辑；右：一句话提示词普通编辑','中：R109一句话提示词普通编辑；右：R110明确绑定原视频的普通编辑')
  s=s.replace('Replace the basketball with a neon-lit basketball.','Edit &lt;Video 1&gt; by changing only the basketball into a neon-lit basketball. Keep the original player, dribbling actions, camera framing, scene, and timing.')
  s=s.replace('原结果使用.9 GPU0，本次使用同机GPU3。','两次均使用.9 GPU3。')
 dst.write_text(s)
(R/'ROOT_HANDOFF.txt').write_text('R110实际成片consumer。左参考，中R109一句话普通编辑，右R110明确绑定Video1与保留要求的普通编辑。\n只有完成实际gate/history/精确进程释放/SHA后下载。展示105有效帧，全16:9画面，去掉模型padding；全18页逐帧证据。\n命令 scripts/consume.py；仅新建一次collection，重做展示使用--build-only。\n')
print(R)
