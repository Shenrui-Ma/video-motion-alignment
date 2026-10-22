"""Portable seven-task report; completed media embedded and every failure retained."""
import argparse,base64,html,time
from common import *
LABELS={'short_0131':'快递员外套改白色','short_0268':'右侧人物替换为男孩','short_0343':'镜前人物替换为医生','short_0274':'宇航员替换为外星人','short_0085':'头发改红色','short_0358':'左侧男子增加眼镜','short_0178':'白衬衫改蓝色'}
STATUSES={'PENDING':'待生成','RUNNING_OR_PENDING':'生成中或等待运行','GENERATION_FAILED':'生成失败','CONSUMER_FAILED':'结果核验或展示处理失败','PRESENTATION_READY':'三栏成片已归档'}
def summary():
    rows=[]
    for source in PAIRS:
        row={'source':source,'title':LABELS[source],'task':entry(source)['edit_prompt'],'status':'PENDING','official_MF':'PENDING','editing_success':'UNREVIEWED','motion_timing':'UNREVIEWED'}
        state=ROOT/'results'/source/'STATUS.json'
        if state.exists():row.update(read(state))
        for name in ('EFFICIENCY','HUMAN_REVIEW'):
            p=ROOT/'results'/source/(name+'.json')
            if p.exists():row[name.lower()]=read(p)
        rows.append(row)
    return {'fixed_denominator':7,'rows':rows,'generated_unix':time.time(),'official_MF_scheduled':False}
def build(output):
    report=summary();blocks=[]
    for row in report['rows']:
        source=row['source'];body='';path=ROOT/'showcase'/source/'PRESENTATION.json'
        if path.exists():
            record=read(path)
            for item in record['videos']:
                if item['name']!='full_valid':continue
                video=ROOT/'showcase'/source/(item['name']+'.mp4');require(sha(video)==item['video']['sha256'],'rendered video changed')
                body+=f'<video controls playsinline preload="metadata" src="data:video/mp4;base64,{base64.b64encode(video.read_bytes()).decode()}"></video>'
            figure=ROOT/'showcase'/source/'six_times.png';require(sha(figure)==record['figure']['sha256'],'rendered figure changed')
            body+=f'<details><summary>查看全片均匀六时刻</summary><img alt="参考、普通编辑、时序引导，同帧对比" src="data:image/png;base64,{base64.b64encode(figure.read_bytes()).decode()}"></details>'
        else:body='<div class="pending">'+html.escape(STATUSES.get(row['status'],row['status']))+'</div>'
        efficiency=row.get('efficiency',{}).get('methods',{})
        timings=''
        if efficiency:
            timings='<p class="small">整条任务用时：'+ '；'.join(('普通编辑' if m=='native' else '时序引导')+f" {efficiency[m]['job_wall_seconds']/60:.1f} 分钟" for m in METHODS)+'。两组均20步。</p>'
        error=f'<details><summary>失败记录</summary><pre>{html.escape(row["error"])}</pre></details>' if row.get('error') else ''
        review=row.get('human_review',{});assessment=html.escape(review.get('summary','编辑是否完成、动作是否改善：待逐组检查。'))
        blocks.append(f'<section id="{source}"><h2>{source} · {LABELS[source]}</h2><p class="task">{html.escape(row["task"])}</p><p class="status">{html.escape(STATUSES.get(row["status"],row["status"]))}</p>{body}{timings}<p>{assessment}</p>{error}</section>')
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench 七组主体与局部编辑对照</title><style>body{margin:0;background:#0a0b0e;color:#eceef3;font:18px/1.6 system-ui}main{max-width:2400px;padding:32px 24px;margin:auto}h1{font-size:32px}h2{font-size:25px;margin-bottom:8px}section{padding:24px 0 40px;border-top:1px solid #333}p{max-width:1450px}.task{color:#b4baca}.small,.status{font-size:15px;color:#a6adbd}video,img{display:block;width:100%;background:black}video{min-height:160px}details{margin:16px 0}summary{cursor:pointer}.pending{padding:60px;background:#14171e;text-align:center;color:#acb3c2}pre{white-space:pre-wrap}nav a{display:inline-block;color:#9bc3ff;margin:0 20px 14px 0}</style><main><h1>IVEBench · 七组主体与局部编辑</h1><p>三列依次为参考视频、普通编辑、编辑＋时序引导。两组采用相同输入、提示词和种子；引导作用于第7至15次去噪计算。各列展示相同物理时刻，保留原视频有效时长。</p><p>七组任务全部列出。先检查原任务是否完成及原场景是否保留，再检查动作阶段和时序。官方 MF 评分另行安排。</p><nav>'''+''.join(f'<a href="#{s}">{s}</a>' for s in PAIRS)+'</nav>'+''.join(blocks)+'</main></html>'
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);temp=output.with_name('.'+output.name+'.tmp');temp.write_text(document);os.replace(temp,output)
    replace(output.with_suffix('.json'),report)
    return {'html':str(output),'sha256':sha(output),'fixed_denominator':7}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();verify_runtime(inputs=False);print(json.dumps(build(a.output)))
