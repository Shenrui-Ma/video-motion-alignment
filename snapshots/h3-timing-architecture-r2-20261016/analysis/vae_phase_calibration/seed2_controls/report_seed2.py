"""Independent final pose comparison; absent intermediate labels stay unknown."""
import csv,datetime,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[3]/'h3-timing-autoresearch-20261016'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(d):
    def selected(key):
        x=d.get(key)
        return None if x is None else {k:x.get(k) for k in ('lag_frames','error','coverage','valid_frame_count')}
    return dict(status=d['status'],flags=d.get('flags'),reliable_lag_frames=d.get('reliable_lag_frames'),
                same_frame=selected('same_frame'),best=selected('best'),unqualified_best=selected('unqualified_best'))


def main():
    result=json.loads((HERE/'RESULTS.json').read_text())
    protocol=json.loads((HERE/'PROTOCOL.json').read_text())
    poses={};sources={};rows=[]
    for mode in ('native','mass'):
        poses[mode]={}
        for threshold in ('0.3','0.5'):
            path=OLD/'analysis/pose/pilot'/f's05_full_seed2_{mode}_x0_00001_.threshold{threshold}.timing.json'
            d=json.loads(path.read_text());sources[str(path)]=sha(path)
            for row in d['diagnostics']:
                key=':'.join(map(str,row['window']))
                poses[mode].setdefault(key,{}).setdefault(threshold,{})[row['feature']]=compact(row)
    for run,entry in result['sources']['05']['runs'].items():
        mode,stage=run.split('/')
        for region,methods in entry['regions'].items():
            for method,records in methods.items():
                for item in records['rows']:
                    lag=item['best']['lag_frames'] if item['best'] else None
                    key=':'.join(map(str,item['window_inclusive']))
                    pose=poses[mode][key] if stage=='sampler_final' else None
                    comparisons=[];strict=False
                    if pose:
                        lags=[pose[t]['arm_direction']['reliable_lag_frames'] for t in ('0.3','0.5')]
                        strict=all(x is not None for x in lags) and abs(lags[0]-lags[1])<=2
                        for threshold,pl in zip(('0.3','0.5'),lags):
                            comparisons.append(dict(threshold=threshold,pose_lag=pl,
                                absolute_error=None if pl is None or lag is None else abs(lag-pl),
                                within2=None if pl is None else bool(item['accepted'] and abs(lag-pl)<=2),
                                false_near_zero=None if pl is None else bool(item['accepted'] and abs(pl)>2 and abs(lag)<=2),
                                false_nonzero=None if pl is None else bool(item['accepted'] and abs(pl)<=2 and abs(lag)>2)))
                    rows.append(dict(run=run,region=region,method=method,window=item['window_inclusive'],
                        latent_lag=lag,accepted=item['accepted'],rejection_reasons=item['rejection_reasons'],
                        score=item['best']['signed_cosine_error'] if item['best'] else None,margin=item['margin'],
                        clamped_frames=item['best']['clamped_frames'] if item['best'] else None,
                        at_search_boundary=abs(lag)==24 if lag is not None else None,
                        pose_status='final_independent_table' if pose else 'unknown_no_same_checkpoint_label',
                        pose=pose,strict_pose_available=strict,
                        strict_within2=all(c['within2'] for c in comparisons) if strict else None,comparisons=comparisons))
    summaries={}
    for region in protocol['regions']:
        summaries[region]={}
        for method in protocol['methods']:
            subset=[r for r in rows if r['region']==region and r['method']==method]
            final=[r for r in subset if r['run'].endswith('/sampler_final')]
            known=[c for r in final for c in r['comparisons'] if c['pose_lag'] is not None]
            strict=[r for r in final if r['strict_pose_available']]
            summaries[region][method]=dict(all_windows=len(subset),accepted=sum(r['accepted'] for r in subset),
                final_windows=len(final),final_strict_pose_known=len(strict),final_strict_within2=sum(r['strict_within2'] for r in strict),
                final_known_threshold_cells=len(known),final_known_threshold_within2=sum(c['within2'] for c in known),
                final_false_near_zero=sum(c['false_near_zero'] for c in known),final_false_nonzero=sum(c['false_nonzero'] for c in known),
                intermediate_unknown=sum(r['pose'] is None for r in subset),
                final_strict_unknown=len(final)-len(strict))
    quality=OLD/'analysis/pose/pilot/TRANSFER05_SEED2_PAIR_REVIEW.md'
    report=dict(schema='h3-seed2-phase-observer-comparison-v1',result_sha256=sha(HERE/'RESULTS.json'),
        protocol_sha256=sha(HERE/'PROTOCOL.json'),pose_inputs=sources,rows=rows,summary=summaries,
        background_quality={'review_path':str(quality),'sha256':sha(quality),'status':'failure_in_both_native_and_mass',
                            'meaning':'Timing agreement is not edit-quality success; native already has altered dark curtain/wall.'},
        intermediate_labels='None found; final label never used as intermediate ground truth.')
    with (HERE/'POSE_COMPARISON.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    with (HERE/'ALL_WINDOWS.csv').open('x',newline='') as f:
        fields=['run','region','method','window','latent_lag','accepted','rejection_reasons','margin','clamped_frames','at_search_boundary','pose_status','pose03','pose05','strict_pose_available','strict_within2']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:
            d={k:row[k] for k in fields if k in row}
            d['pose03']=row['comparisons'][0]['pose_lag'] if row['comparisons'] else None
            d['pose05']=row['comparisons'][1]['pose_lag'] if row['comparisons'] else None
            w.writerow(d)
    lines=['第二seed现成快照：冻结VAE相位观察器必要性检查','',
        '结论：第二seed最终结果中，两方法在全部已有姿态可判格都符合固定两帧容差；没有把native的大延后读成近零，也没有把mass的近零读成明显延后。中间去噪阶段没有独立标签，不能判对错。两臂都已有背景保存失败，不能称正常编辑或整体成功。','',
        '输入核验：29项通过。native/mass以及seed1的实际原RGB、VAE prepared frames/latents、Qwen presentation/embedding、token tags、prompt、目标shape、packed layout均一致，仅去掉tensor_file路径再比较。seed2两臂实际噪声一致、seed=2026101312。10份快照文件与远端SHA一致，视频/音频raw tensor与capturemanifest一致；参考rawSHA与每条真实conditioning匹配。','',
        '规则未变：全画面主结果、原视频固定上身ROI敏感性；两个方法phase_mean_centering/same_phase_gap5；四窗50–65/69–81/80–92/99–111；±24物理帧搜索，原拒判阈值，所有49点曲线保留。每个step为0-based去噪调用，不是视频帧。','',
        '全部读出（数组依次为四个固定窗口）：']
    for run,entry in result['sources']['05']['runs'].items():
        meta=entry['snapshot_metadata']
        lines.append(f"{run}: model_call={meta.get('model_call_one_based')}, sigma_video={meta.get('sigma_video')}, sigma_audio={meta.get('sigma_audio')}")
        for region,methods in entry['regions'].items():
            for method,data in methods.items():
                lines.append('  '+region+' / '+method+': '+str([r['best']['lag_frames'] if r['best'] else None for r in data['rows']]))
    lines += ['', '最终pose原表（.3/.5置信度；不是两个独立实验）：',
              'native方向：[15,15,16,17] / [15,unknown,16,17]；mass方向：[-1,-2,-1,-1] / [-1,unknown,-1,-1]。',
              '每方法每ROI：最终严格双阈值可判6/8窗，6/6在两帧内；单阈值已知14/16格，14/14在两帧内。第二窗的高阈值继续unknown，不用低阈值填补。',
              '全部160个latent窗口均被原退化门接受，无端点clamp或搜索边界。不能据此声称置信度充分；本次没有形成新的拒判反例。',
              '', '中间阶段边界：',
              '全部128个中间格没有相同checkpoint的独立pose标签。native持续读出约+13到+17，mass全画面约−2到0，这只是轨迹读出。不能拿最终pose作为这些时刻真值。',
              '一个需保留的例外：mass step005的上身ROI/gap5在主窗读到−3（超出near-zero±2），全画面同方法为−2；当前没有早期标签，不能说ROI误报已被证实，也不能事后换ROI避免它。',
              '', '质量混杂：',
              '已有独立视觉审查确认，两臂均把大片白色窗帘/墙面改成黑色。native已坏，不能说mass新引入了背景泄漏。即使时间相位正确，单一动作读出也不能判断编辑身份、背景、画质、手指或整体连贯性。',
              '这是同一素材的第二随机种子，不是新场景。step019与final来自相邻端点，不是独立样本。5bin差分仍跨17帧，不能据本结果证明短动作粒度；去相位均值也仍可能删真实周期运动。',
              '', '最小补证建议（未启动任何推理）：',
              '最便宜的正常最终态控制是复用已知动作基本正常的1024 native MP4，后续单独VAE重编码 source和output并同时保留原RGB pose/quality判断；这只验证重新编码后的最终态，不能替代真实采样x0，不可与本次snapshot精度无区别合并。',
              '若必须检验早期误触发，最少需要一次预先固定的新素材native运行，被动保存同样的step005/010/015/019/final。先只根据源视频定义窗口/ROI/geometry，再执行一次固定seed；不根据生成结果抽卡筛选。独立pose与背景质量通过且lag近零后才构成正常控制。1024旧素材重放也可作为廉价必要检查，但仍不是独立场景。',
              '新增正常例应在计算latent观察器前冻结评估；同时保留失败/延后结果，不能只保留恰好正常的片子。不要因为本次全部接受就调margin或改方向阈值。',
              '', f"验证：3项新CPU provenance契约测试通过；复用冻结方法/输入校验。计算{result['elapsed_seconds']:.3f}秒，CUDA_initialized={result['CUDA_initialized']}。无GPU、无新模型、无VAE重编码、无DWPose调用。"]
    (HERE/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
    checks={'160_rows':len(rows)==160,'128_intermediate_unknown':sum(r['pose'] is None for r in rows)==128,
            'no_pose_labels_read_during_latent_scoring':result['pose_labels_read'] is False,
            'no_GPU':result['CUDA_initialized'] is False,
            'all_49_point_curves':all(len(r['curve'])==49 for e in result['sources']['05']['runs'].values() for reg in e['regions'].values() for m in reg.values() for r in m['rows']),
            'frozen_method_unchanged':sha(protocol['method_source'])==protocol['method_source_sha256'],
            'frozen_evaluator_unchanged':sha(protocol['loader_path'])==protocol['loader_sha256']}
    if not all(checks.values()):raise RuntimeError(checks)
    (HERE/'QA.json').write_text(json.dumps(checks,indent=2)+'\n')
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=HERE/'manifest.json')
    manifest=dict(schema='h3-seed2-phase-observer-freeze-v1',frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files={str(p.relative_to(HERE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files},
        CPU_only=True,all_windows_and_unknowns_preserved=True)
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(summaries,indent=2));print('QA PASS. Manifest SHA',sha(HERE/'manifest.json'))


if __name__=='__main__':main()
