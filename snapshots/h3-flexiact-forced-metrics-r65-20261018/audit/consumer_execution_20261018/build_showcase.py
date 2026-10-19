"""Build an embedded presentation from verified actual R65 artifacts only."""
import argparse
import base64
import hashlib
import html
import json
import mimetypes
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def data(path):
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()

def lag(row):
    if row['status'] != 'qualified_exploratory':
        return 'UNKNOWN'
    values = row['lag_ms_at_confidence_03_05']
    return ' / '.join(f'{v:+d}' for v in values)+' ms'

def page(sources, destination):
    contract=read(ROOT/'configs/producer_scientific_contract.json')
    sections=[]
    for source in sources:
        case=next(c for c in contract['cases'] if c['source_id']==source and c['arm']=='native')
        intake=ROOT/'incoming'/source
        gate=read(intake/'PAIR_RUNTIME_GATE.json')
        assert gate['passed'] is True and all(gate['checks'].values())
        portrait=ROOT/'inputs'/case['portrait']
        assert sha(portrait)==case['portrait_sha256']
        presentation=read(ROOT/'showcase'/f'{source}_PRESENTATION.json')
        assert presentation['input_gate']['sha256']==sha(intake/'PAIR_RUNTIME_GATE.json')
        title={'fitness':'Fitness · 健身动作','one_leg':'One-leg · 单脚动作'}[source]
        videos=[]
        for name,count,label in [('first2seconds',48,'前 2 秒'),('full_valid',147,'完整有效片段 · 6.125 秒')]:
            video=ROOT/'showcase'/f'{source}_{name}.mp4'
            record=next(v for v in presentation['videos'] if Path(v['video']['file']).name==video.name)
            assert record['physical_frame_interval']==[0,count-1] and sha(video)==record['video']['sha256']
            download=destination.parent/f'H3_FlexiAct_{source}_{name}_三栏对照_20261018.mp4'
            if download.exists():
                assert sha(download)==sha(video), 'preserve a different existing download'
            else:
                shutil.copy2(video,download)
            videos.append(f'<div class="clip"><h3>{label}</h3><video controls playsinline loop preload="metadata" src="{data(video)}"></video></div>')
        mf=[]
        for method in ('native','forced'):
            path=ROOT/'scores'/method/source/'SCORE.json'
            if path.exists():
                score=read(path)
                assert score['pair_id']==f'human/{source}/000'
                mf.append(f"{score['score']:.4f}" if score['status']=='finite' else 'UNKNOWN')
            else:
                mf.append('评测中')
        physical=ROOT/'scores/physical'/f'{source}.json'
        rows=[]
        if physical.exists():
            report=read(physical)
            assert report['producer_gate']['sha256']==sha(intake/'PAIR_RUNTIME_GATE.json')
            for entry in report['result']['paired_lag_summary']:
                w=entry['window']; feature=entry['feature']
                if w==[0,15] or (w==[0,48] and feature=='arm_direction'):
                    time_label='前 2 秒' if w==[0,15] else '完整片段'
                    part={'arm_direction':'双臂','left_arm_direction':'左臂','right_arm_direction':'右臂'}[feature]
                    rows.append(f'<tr><td>{time_label} · {part}</td><td>{lag(entry["methods"]["native"])}</td><td>{lag(entry["methods"]["forced"])}</td></tr>')
        timing=('<div class="tablewrap"><table><thead><tr><th>动作时差</th><th>普通编辑</th><th>固定时序引导</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><p class="small">正值表示动作延后。两个数依次对应姿态置信阈值 0.3 / 0.5；时间分辨率为 125 ms。UNKNOWN 表示当前姿态观测不足以给出可靠时差。</p>') if rows else '<p class="small">动作时差评测进行中。</p>'
        notes=Path(__file__).with_name('CASE_CONCLUSIONS.json')
        conclusion=read(notes).get(source) if notes.exists() else None
        conclusion_html='<p><b>'+html.escape(conclusion['text'])+'</b></p>' if conclusion else ''
        sections.append(f'<section><div class="casehead"><div><h2>{title}</h2><p>目标人物参考图</p><img class="portrait" src="{data(portrait)}" alt="{html.escape(source)} 的目标人物参考图"></div><div class="caseinfo"><p>三列依次为参考视频、普通编辑、固定时序引导。</p><p>同一输入、目标人物、提示词和随机种子；前 6 次去噪预测已逐张量核对一致。</p><p>官方 MF：普通编辑 <b>{mf[0]}</b> · 固定时序引导 <b>{mf[1]}</b></p>{conclusion_html}</div></div>'+''.join(videos)+timing+'</section>')
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlexiAct 固定时序引导对照</title><style>
    *{box-sizing:border-box}body{margin:0;background:#101112;color:#eee;font:17px/1.7 system-ui,-apple-system,"PingFang SC",sans-serif}main{max-width:2600px;margin:auto;padding:28px 24px 64px}h1{font-size:30px;margin:0 0 12px}h2{font-size:25px;margin:0 0 12px}h3{font-size:18px;font-weight:500;color:#ddd;margin:18px 0 10px}p{margin:8px 0;color:#c6c6c6}header{max-width:1100px;margin-bottom:32px}section{border-top:1px solid #3b3b3b;padding-top:24px;margin-top:42px}.casehead{display:flex;gap:40px;align-items:center;margin-bottom:24px}.caseinfo{max-width:860px}.portrait{display:block;width:auto;max-width:300px;height:160px;object-fit:contain;object-position:left center;background:#000}video{display:block;width:100%;max-height:84vh;background:#000}.clip{margin-bottom:28px}table{border-collapse:collapse;min-width:620px;margin-top:20px}td,th{text-align:left;padding:10px 20px;border-bottom:1px solid #343434;font-weight:400}th{color:#a7a7a7}.small{font-size:14px;color:#a7a7a7;max-width:1100px}.tablewrap{overflow:auto}@media(max-width:650px){main{padding:18px 12px}.casehead{display:block}.caseinfo{margin-top:16px}h1{font-size:24px}.portrait{height:130px}}
    </style><main><header><h1>FlexiAct · 固定时序引导对照</h1><p>在预定采样区间加入按视频时刻对应的参考信息，比较动作时间与换人效果。本页使用此前已观察过的开发样例。</p><p class="small">各列按相同物理时间播放。完整展示为有效的 147 帧；官方参考视频为 8 fps，输入中每帧重复为 3 帧。原始 158 帧成片及末尾填充保留在实验归档。</p><p class="small">MF 衡量轨迹位移方向的匹配程度。动作延后由姿态时差和同帧视频另行检查；人物与场景编辑效果以参考图和成片为依据。</p></header>'''+''.join(sections)+'</main></html>'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(document)
    return {'html':str(destination),'sha256':sha(destination),'sources':sources,'actual_video_count':2*len(sources),'fully_embedded':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',action='append',choices=['fitness','one_leg'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(page(args.source,args.output),ensure_ascii=False,indent=2))
