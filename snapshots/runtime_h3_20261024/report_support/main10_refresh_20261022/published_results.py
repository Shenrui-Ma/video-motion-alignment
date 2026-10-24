"""Render verified public score tables, keeping benchmark scopes and scales explicit."""
import html

def render_published_results(data, means):
    esc=lambda v:html.escape(str(v),quote=True)
    fmt=lambda v:'未公开' if v is None else f'{v:.4f}'
    columns=data['metric_order']
    meanings={'SC':'主体一致性','BC':'背景一致性','TF':'闪烁质量','MS':'运动平滑','VTSS':'综合画质','OSC':'整体语义一致','PSC':'编辑短语一致','IS':'指令完成','QA':'数量准确','SF':'语义保真','MF':'运动保真','CF':'内容保真','Total':'总分','Quality':'质量','Compliance':'指令遵循','Fidelity':'保真度','Motion':'运动（原文列名）','Sem. Consist.':'语义一致（原文列名）','Content':'内容保真'}
    def heading(value):
        key=value.removesuffix(' ↑').replace(' 原始分','').replace(' Δ','')
        return esc(value)+('<small class="metric-cn">'+meanings[key]+'</small>' if key in meanings else '')
    keymap={'SC':'subject_consistency','BC':'background_consistency','TF':'temporal_flickering','MS':'motion_smoothness','VTSS':'vtss','OSC':'overall_semantic_consistency','PSC':'phrase_semantic_consistency','IS':'instruction_satisfaction','QA':'quantity_accuracy','SF':'semantic_fidelity','MF':'motion_fidelity','CF':'content_fidelity'}
    def table(headers, rows, css=''):
        return '<div class="scroll"><table '+css+'><thead><tr>'+''.join('<th>'+heading(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    out=['<section class="intro" id="paper-comparison"><h2>公开论文结果</h2>',
         '<p>官方评测含400条short、200条long；本实验采用其中9条混合子集（6条short、3条long）。以下按各自样本范围分表：本实验MF显示相对参考差值，公开论文MF保留原始分数。各项分母随任务适用性变化，官方未逐项公布。</p>',
         '<h3>本实验 · IVEBench 9条混合子集</h3>']
    rows=[]
    for method,label in [('native','H3 普通编辑'),('global_weak','H3 全程弱引导')]:
        values=[]
        for metric in columns:
            record=means[method][keymap[metric]]
            if metric=='MF' and record.get('mean') is not None:
                values.append(f"{means[method]['motion_fidelity_delta_from_reference']['mean']:+.4f}")
            else:
                values.append(fmt(record.get('mean')) if record.get('mean') is not None else ('N/A' if metric=='QA' else '待Qwen72B资源'))
        rows.append([label,'9（6 short＋3 long）']+values)
    out.append(table(['方法','样本范围']+[x+(' Δ' if x=='MF' else ' ↑') for x in columns],rows,'data-score-table="ours-ive9"'))
    out.append('<p class="muted">九项数值均采用9/9组；本实验逐样本差值与各区间比较见页首。</p>')
    for subset,n in [('short',400),('long',200)]:
        out.append(f'<details><summary>IVEBench官方评测 · {subset} · {n}条 · 8种方法</summary><p class="muted">数据来源：<a href="https://ryanchenyn.github.io/projects/IVEBench/" target="_blank" rel="noopener">IVEBench官方排行榜</a>；配置见<a href="https://arxiv.org/html/2510.11647v2#Sx4" target="_blank" rel="noopener">论文附录D</a>。</p>')
        rows=[]
        for row in data['official_leaderboard']:
            if row['subset']!=subset:continue
            count=f"{row['processed_videos']}/{row['dataset_size']}"
            if row['excluded_oom_videos']:count+=f"（OOM跳过{row['excluded_oom_videos']}）"
            rows.append([row['method'],count,row['resolution']]+[fmt(row['metrics'].get(x)) for x in columns])
        assert len(rows)==8
        out.append(table(['方法','成功生成 / 子集','分辨率']+[x+(' 原始分' if x=='MF' else ' ↑') for x in columns],rows,f'data-score-table="official-{subset}"'))
        out.append('</details>')
    out.append('<details><summary>EditVid论文 · IVEBench四项聚合指标</summary><p class="muted"><a href="https://arxiv.org/html/2609.04190v1#S5.T3" target="_blank" rel="noopener">EditVid表3</a>按官方协议报告Total、Quality、Compliance和Fidelity；该表未列样本数和short／long拆分。FiVE上的MFS属于另一数据集，保留在原论文的独立评测中。</p>')
    rows=[[r['method'],'是' if r['training_free'] else '否']+[fmt(r['aggregate_scores'][k]) for k in ['total','quality','compliance','fidelity']] for r in data['editvid_paper_aggregate']]
    out.append(table(['方法','Training-free','Total ↑','Quality ↑','Compliance ↑','Fidelity ↑'],rows,'data-score-table="editvid-aggregate"'))
    out.append('</details>')
    out.append('<details><summary>AVE论文 · 原文报告值</summary><p class="muted"><a href="https://arxiv.org/html/2610.11037v1" target="_blank" rel="noopener">AVE表2、表3</a>采用short／long协议，实际成功样本数未列出。表中保留原文数值尺度；Motion列的名称与正文指标说明有歧义，沿用原标签。Content为1–5分。</p>')
    keys=['total','quality','compliance','fidelity','Motion','Sem. Consist.','Content']
    rows=[['AVE',r['subset']]+[fmt(r['original_reported_scores'][k]) for k in keys] for r in data['ave_paper']]
    out.append(table(['方法','子集','Total','Quality','Compliance','Fidelity','Motion','Sem. Consist.','Content'],rows,'data-score-table="ave-original"'))
    out.append('</details></section>')
    return ''.join(out)
