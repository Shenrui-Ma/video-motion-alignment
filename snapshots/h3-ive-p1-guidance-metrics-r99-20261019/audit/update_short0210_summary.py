from pathlib import Path
import base64, hashlib, json, re

root=Path(__file__).resolve().parents[1]
page=Path('/Users/researcher/Downloads/H3_R99_short_0210_普通编辑与时序引导_20261019.html')
review=root/'audit/agent_full_review_short0210/REVIEW.json'
result=Path('/Users/researcher/DevProjects/h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/R99_0210_RESULT_VERIFIED.json')
v=json.loads(result.read_text());r=json.loads(review.read_text())
assert r['reviewed_frames']==list(range(87)) and v['valid_frames']==87
for role,path in v['paths'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==v['score_sha256'][role]
assert abs(v['forced']-v['native']-v['delta'])<1e-12
old=page.read_text();assert 'id="actual-review"' not in old
assets=lambda s:[hashlib.sha256(base64.b64decode(x)).hexdigest() for x in re.findall(r'data:[^;,]+;base64,([A-Za-z0-9+/=]+)',s)]
summary=f'''<section id="actual-review"><h2>结果</h2><p>两版均完成男性替换，保留舞台、服装和主要手势。检查全部87个有效帧后，普通编辑已基本对齐，引导版未见明确时序改善。</p><p>IVEBench官方Motion Fidelity（越高越好）：普通编辑 <b>{v['native']:.4f}</b>，时序引导 <b>{v['forced']:.4f}</b>，变化 <b>{v['delta']:+.4f}</b>。该分数评价运动轨迹，角色替换是否完成由完整视频另行检查。</p><p>本次引导采用固定去噪步骤6–14的同时间参考读取。此处展示已知固定方案的配对效果，自动选择干预时机的实验另行记录。</p></section>'''
new=old.replace('<video controls',summary+'<video controls',1)
assert assets(new)==assets(old)
out=root/'audit/short0210_summary_update';out.mkdir(exist_ok=True)
(out/'previous.html').write_text(old);page.write_text(new)
(out/'RECEIPT.json').write_text(json.dumps({'page':str(page),'sha256':hashlib.sha256(page.read_bytes()).hexdigest(),'review_sha256':hashlib.sha256(review.read_bytes()).hexdigest(),'metric_receipt_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'embedded_asset_sha256':assets(new),'UI_review':'not assessed; browser disabled'},ensure_ascii=False,indent=2)+'\n')
print('summary and measured scores added; embedded media bytes verified')
