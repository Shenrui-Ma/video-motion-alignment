"""Use the existing renderer for source / R121 sentence / R123 task envelope."""
import base64,html,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import render_pair

def main():
    validate_static();gate=verify_intake('short_0358');p=info('short_0358')
    previous=ROOT.parent/'h3-ive-official-positive-recheck-metrics-r121-20261020'
    old=previous/'incoming/short_0358';old_gate=read(old/'NATIVE_RUNTIME_GATE.json')
    old_inputs=read(previous/'prepared/short_0358/native/MF_INPUTS.json')
    assert old_gate['passed'] and old_gate['runs']['native']['routed_blocks']==0
    assert old_inputs['raw_videos']['native']['sha256']==sha(old/'native.mp4')==old_gate['runs']['native']['video']['sha256']
    assert old_inputs['raw_videos']['source']['sha256']==p['source']['sha256']
    assert old_inputs['valid_frames']==105 and old_inputs['crop_xywh']==p['crop_xywh']
    actual=read(ROOT/'incoming/short_0358/native_graph.json')
    bare=read(old/'native_graph.json')
    assert bare['5']['inputs']['prompt']==p['original_task']['edit_prompt']
    verify_official_prompt(p,actual)
    assert gate['checks']['native_r121_initial_noise_equal']
    dest=ROOT/'showcase_prompt_control/short_0358';dest.mkdir(parents=True,exist_ok=True)
    receipt=dest/'PRESENTATION.json'
    if receipt.exists():print(json.dumps(bound(receipt)));return
    inputs=[ROOT/p['source']['file'],old/'native.mp4',ROOT/'incoming/short_0358/native.mp4']
    render_pair.LABELS=('1.参考视频','2.官方原句','3.任务格式 + 官方原句')
    media=render_pair.render_files(inputs,dest,107,105,render_pair.choose_font(),'/opt/homebrew/bin/ffmpeg','/opt/homebrew/bin/ffprobe')
    original=dest/media['videos'][0]['file'];video=dest/'source_bare_envelope_full105.mp4';original.rename(video)
    media['videos'][0]['file']=video.name
    still=dest/'same_frame_038.jpg'
    subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(video),'-vf','select=eq(n\\,38)','-frames:v','1','-q:v','2',str(still)],check=True)
    proof={'schema':'r123-prompt-format-control-v1','columns':['source','r121_bare_native','r123_envelope_native'],
           'source_count':1,'guidance_in_this_comparison':False,'valid_frames':105,'fps':24,
           'input_media':[bound(x)for x in inputs],'previous_gate':bound(old/'NATIVE_RUNTIME_GATE.json'),
           'new_gate':bound(ROOT/'incoming/short_0358/NATIVE_RUNTIME_GATE.json'),
           'actual_prompts':[bare['5']['inputs']['prompt'],actual['5']['inputs']['prompt']],
           'initial_noise_equal':True,'caption_labels':list(render_pair.LABELS),'still':dict(**bound(still),frame=38),
           'render_script':bound(__file__),**media}
    save(receipt,proof)
    title='饮酒加眼镜：提示词格式对照'
    uri='data:video/mp4;base64,'+base64.b64encode(video.read_bytes()).decode()
    output=Path('/Users/researcher/Downloads/H3_R123_饮酒提示词格式对照_20261020.html')
    text=f'<!doctype html><html lang="zh"><meta charset="utf-8"><title>{title}</title><style>body{{background:#111;color:#eee;max-width:1800px;margin:25px auto;font:18px system-ui}}video{{width:100%}}pre{{white-space:pre-wrap}}</style><h1>{title}</h1><p>同一参考视频、种子和初始噪声。两版均为普通编辑，比较任务格式标识对编辑结果的影响。</p><video controls loop src="{uri}"></video>'
    for label,prompt in zip(render_pair.LABELS[1:],proof['actual_prompts']):text+=f'<details><summary>{label}</summary><pre>{html.escape(prompt)}</pre></details>'
    output.write_text(text+'</html>');save(dest/'HTML.json',bound(output));print(json.dumps({'presentation':bound(receipt),'html':bound(output)}))

if __name__=='__main__':main()
