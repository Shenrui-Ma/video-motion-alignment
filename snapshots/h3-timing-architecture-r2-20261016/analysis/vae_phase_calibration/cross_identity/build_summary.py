"""Summarize every frozen cell without selecting a new method or ROI."""
import datetime
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    result=json.loads((HERE/'RESULTS.json').read_text())
    comparison=json.loads((HERE/'POSE_COMPARISON.json').read_text())
    protocol=json.loads((HERE/'PROTOCOL.json').read_text())
    lines=[
        'H3 跨身份 latent 时间相位观察器：固定规则必要性检验',
        '',
        '主结果：固定5bin差分通过了本轮可与独立姿态对照的精度格；全画面去相位均值法没有通过全部两帧精度门。两者均尚未证明早期主窗的整体可观测性或闭环控制有效。',
        '',
        '范围和计数：旧 source05、source07，均为参考人物到Sam的编辑；native和全程同帧mass两条轨迹。source05读取step005/010/015/final，source07仅final。两方法、两ROI，共152个窗口读出，不是152个独立样本。',
        'source05四窗依次50–65、69–81、80–92、99–111；source07三窗依次54–69、75–88、98–111。窗口和lag以24fps物理视频帧计。step005指第6次去噪模型调用，不是视频第5帧。',
        '全画面为主结果；上身ROI来自原视频固定姿态范围，只作敏感性，不能用于事后挽救主门。两方法及拒判阈值均继承此前冻结控制实验，未调参。',
        '',
        '完整读出（数组依次对应本素材全部预定窗口；正数表示编辑视频更晚）：',
    ]
    for source,data in result['sources'].items():
        lines.append('source'+source)
        for run,info in data['runs'].items():
            meta=info['snapshot_metadata']
            lines.append(f"  {run}; model_call={meta.get('model_call_one_based')}; sigma_video={meta.get('sigma_video')}; sigma_audio={meta.get('sigma_audio')}")
            for region,methods in info['regions'].items():
                for method,records in methods.items():
                    lags=[r['best']['lag_frames'] if r['best'] else None for r in records['rows']]
                    rejections=[r['rejection_reasons'] for r in records['rows']]
                    lines.append(f'    {region} / {method}: {lags}; reject={rejections}')
    lines.extend(['', '独立姿态对照（unknown不填0、不拿最终视频代替中间x0真值）：'])
    for region,methods in comparison['summary'].items():
        for method,stages in methods.items():
            for stage,v in stages.items():
                lines.append(f"{region} / {method} / {stage}: 完整pose可用{v['strict_pose_available']}/{v['total_windows']}窗；两帧精度通过{v['strict_within2']}/{v['strict_pose_available']}；其余{v['strict_pose_unavailable']}窗完整pose未知；单阈值已知格精度{v['known_threshold_within2']}/{v['known_threshold_cells']}。")
    lines.extend([
        '最终主结果可判的7窗是两个阈值均有方向lag且相差≤2；中间可判14窗还沿用独立pose的方向/腕位置一致性门。重复阈值格与同视频多个去噪快照不算独立样本。',
        '原最终MP4与离线x0解码再编码的pose置信度可略有差别；final使用原pilot报告，early使用对应x0快照报告，未混用更有利的一张表。',
        '',
        '明确失败：全画面phase_mean_centering的source05 native最终主窗为+10，独立pose为+13/+13，误差3；末窗+1对+4/+4，也误差3。不能调宽原门后写成通过。相应中间stage也出现同类误差。上身ROI虽然更准，仅保留为敏感性。',
        '5bin差分：最终已知双阈值7/7窗和中间完整pose可判14/14窗均在两帧容差内；原始单阈值已知格分别20/20和39/39。未判读的7个最终窗和10个中间窗仍未知。其跨17帧(约0.708秒)的时间平均代价未消除；不能据此证明单个短动作保真。',
        '',
        '低lag误报检查：每方法每ROI在最终已知近零pose的12个阈值格及early的21个阈值格中，均未出现|latent lag|>2的非零方向误报。这些主要是mass修正后的轨迹，并非独立native正常测试集。全部152格都过了固定退化/歧义门，没有搜索边界或端点clamp；这也说明当前门只排除退化，不是准确率置信度。',
        '',
        '早期step005主窗的独立证据边界：',
        '双臂方向两阈值都unknown；same-frame coverage分别0.65625/0.453125。双腕位置也是unknown，coverage0.75/0.53125。整体门仍是unknown_or_confounded。',
        '左臂单独通道可判：.3阈值+13且coverage1.0；.5阈值+12且coverage0.84375；这支持延后方向的辅助证据。右臂coverage仅0.3125/0.0625，不能用左臂替换原整体门。全画面latent两方法均+10，上身均+11；因此至多支持继续验证粗延后信号，不证明早期整体精确phase。',
        '同一step005的第二窗双臂方向在.3阈值+9，.5未知；第三窗.3为+8，.5未知且腕未知；末窗方向+4/+4、腕+4/+4，可独立判读。完整通道status/flags/coverage均保留POSE_COMPARISON.json。',
        '',
        '已有反例资源检查（只读，不运行新推理或新编码）：',
        '1024正常对照的原图未装H3X0Readout，远程也没有对应x0目录。其reference[1,24,42,36,64]仍在；无法直接获得同规范目标x0，不能把MP4当现成latent。',
        '第二seed在transfer0已有native/mass的step005/010/015/019/final十份快照，共享参考raw SHA与本source05一致，可直接CPU评估，不需新GPU。该seed的已知背景质量不佳，适合反例/稳健性必要检查，不能称整体质量正常。目录与manifest核验见existing_controls_inventory.json；本轮未计算该seed读出。',
        '',
        '可继续的假说：精确lag估计与“是否明显延后、是否应触发”是不同任务。当前+10对pose+13在原精度门失败，但可成为下一轮预先冻结粗方向/触发规则的动机；必须保留本次失败，并增加独立近零/错误方向/周期动作反例，不能只改阈值使已有结果通过。',
        '本次无新公式创新或控制器实现。整个当前x0视频可供离线相位均值计算，未使用未来去噪状态；但phase均值可能移除真实周期运动，gap5可能合并短动作。跨空间/身份的像素对应依然没有解决。',
        '',
        f"执行：5个新CPU输入/归一化/哈希/ROI契约测试通过；复用已冻结7个控制单测。计算{result['elapsed_seconds']:.3f}秒，CUDA_initialized={result['CUDA_initialized']}。12份参考/目标文件及raw tensor SHA经核验，reference还与每条实际conditioning审计绑定。无新GPU、VAE编码或pose调用。",
    ])
    (HERE/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
    all_rows=comparison['rows']
    checks={
        'protocol_sha_matches':sha(HERE/'PROTOCOL.json')==result['protocol_sha256'],
        'comparison_binds_result':sha(HERE/'RESULTS.json')==comparison['latent_results_sha256'],
        'complete_152_windows':len(all_rows)==152,
        'all_49_point_curves':all(len(r['curve'])==49 for s in result['sources'].values() for run in s['runs'].values() for region in run['regions'].values() for m in region.values() for r in m['rows']),
        'no_GPU_initialized':result['CUDA_initialized'] is False,
        'all_unknown_preserved':sum(not r['strict_pose_available'] for r in all_rows)==68,
        'frozen_parent_method_unchanged':sha(protocol['method_source'])==protocol['method_source_sha256'],
        'zero_pose_reads_in_latent_scoring':result['pose_labels_read'] is False,
    }
    if not all(checks.values()):raise RuntimeError(checks)
    (HERE/'QA.json').write_text(json.dumps(checks,indent=2)+'\n')
    files=sorted(p for p in HERE.iterdir() if p.is_file() and p.name!='manifest.json')
    manifest=dict(schema='h3-cross-identity-phase-observer-freeze-v1',
                  frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files},
                  no_new_model_execution=True,all_methods_and_failed_unknown_cells_retained=True)
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('QA PASS. Manifest SHA256',sha(HERE/'manifest.json'))


if __name__=='__main__':main()
