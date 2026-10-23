from pathlib import Path
p=Path(__file__).with_name('build.py');s=p.read_text()
s=s.replace("def table(sids):",'''annotations={sid:json.loads((D/'visual'/sid/'ANNOTATION.json').read_text()) for sid in ['short_0252','short_0358']}
def event_table(sid):
 a=annotations[sid];out='<h3>关键动作偏移</h3><table><tr><th>动作</th>'+''.join('<th>'+x+'</th>' for x in labels[1:])+'</tr>'
 for e in a['events']:
  out+='<tr><th>'+e['label']+'</th>'+''.join(f"<td>{e['offset_frames'][m]:+.1f}帧</td>" for m in methods[1:])+'</tr>'
 means=a.get('means',a.get('mean_absolute_offset_frames'))
 out+='<tr><th>平均绝对偏移 ↓</th>'+''.join(f'<td>{means[m]:.2f}帧</td>' for m in methods[1:])+'</tr></table>'
 out+='<p>'+a['visual_conclusion']+'</p>'
 return out

def evidence(sid):
 frames=[52] if sid=='short_0252' else [42,85]
 out=''
 for f in frames:
  data=base64.b64encode((D/'visual'/sid/f'comparison_frame_{f:03d}.jpg').read_bytes()).decode()
  caption='参考与全程α = 0.25已抓住面罩杯，Baseline与部分RoPE频带仍在准备抬手。' if sid=='short_0252' else ('部分RoPE频带的瓶口到嘴时刻接近参考；Baseline仍在举瓶。' if f==42 else '参考与全程α = 0.25已结束饮酒，Baseline与部分RoPE频带仍在饮酒。')
  out+=f'<figure style="margin:16px 0"><img style="width:100%" src="data:image/jpeg;base64,{data}"><figcaption class="sub">第{f}帧。{caption}</figcaption></figure>'
 return out

def table(sids):''')
s=s.replace("out='<div class=\"scroll\"><table><thead><tr><th>方法</th>'","out='<div class=\"scroll\"><table><thead><tr><th>方法</th><th>动作偏移 ↓<small>平均绝对偏移·帧</small></th>'")
s=s.replace("out+=f'<tr><th>{label}</th>'", "mean=sum(annotations[sid].get('means',annotations[sid].get('mean_absolute_offset_frames'))[method] for sid in sids)/len(sids)\n  out+=f'<tr><th>{label}</th><td>{mean:.2f}</td>'")
s=s.replace('<video controls playsinline preload="metadata"', '{evidence(sid)}<video controls playsinline preload="metadata"')
s=s.replace('<p>{result}</p>{table([sid])}', '<p>{result}</p>{event_table(sid)}{table([sid])}')
s=s.replace('QA在这两项任务中不适用；', '动作偏移由逐帧视觉标注得到，正数为延后，负数为提前；采用相同事件过渡区间的中点差，范围记录在原始标注中。QA在这两项任务中不适用；')
p.write_text(s)
