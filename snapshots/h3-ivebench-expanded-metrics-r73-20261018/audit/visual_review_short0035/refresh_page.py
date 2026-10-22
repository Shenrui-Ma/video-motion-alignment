"""Render frozen R73 page, then add bound full-frame qualitative review text."""
from pathlib import Path
import hashlib,html,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read,sha,SELECTION,verify_runtime
from make_showcase import build
OUTPUT=Path('/Users/researcher/Downloads/H3_IVEBench_P1五条新素材_固定引导_20261018.html')
def refresh():
 review_path=HERE/'REVIEW.json';r=read(review_path)
 assert sha(Path(r['actual_gate']['file']))==r['actual_gate']['sha256']
 meta={'source':'short_0035','source_selection_sha256':sha(SELECTION),'editing_success':'普通编辑与固定引导均完成灯条改红，桌面和显示器构图保留。','motion_preservation':'手部入镜、下降到键盘、连续打字的大阶段接近参考；全70帧未见固定引导的明确时序改善。单次按键时刻UNKNOWN。','review':{'file':str(review_path),'sha256':sha(review_path)},'actual_gate':r['actual_gate'],'scope':'探索性全70帧视觉复核；1条任务','fine_finger_timing':'UNKNOWN'}
 path=ROOT/'results/short_0035/HUMAN_REVIEW.json';path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():assert read(path)==meta,'keep existing review and request coordinated merge'
 else:path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 verify_runtime();before=sha(OUTPUT) if OUTPUT.exists() else None;build(OUTPUT)
 text=OUTPUT.read_text();needle='<section><h2>short_0035 · ';start=text.index(needle);end=text.index('</h2>',start)+len('</h2>')
 paragraph='<p class="visual-review">'+html.escape(meta['editing_success'])+' '+html.escape(meta['motion_preservation'])+' 三列均在准备后第18帧（0.750秒）首次出现手；随后进入打字的大阶段接近。此处判断覆盖70帧，属于一条配对任务。</p>'
 text=text[:end]+paragraph+text[end:];OUTPUT.write_text(text)
 assert text.count('class="visual-review"')==1 and text.count('<video ')==10 and '单次按键时刻UNKNOWN' in text
 receipt={'html':str(OUTPUT),'before_html_sha256':before,'html_sha256':sha(OUTPUT),'metadata':{'file':str(path),'sha256':sha(path)},'review_sha256':sha(review_path),'all_five_tasks_retained':True,'embedded_videos':text.count('<video '),'scientific_scripts_changed':False}
 (HERE/'PAGE_UPDATE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':refresh()
