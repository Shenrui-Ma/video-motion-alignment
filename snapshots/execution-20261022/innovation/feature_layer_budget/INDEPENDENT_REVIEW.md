# 因果层预算独立审查

审查者：非本包作者；只读方法源码与 CPU 测试，未修改实现、部署图或队列。

## 结论

主机制符合设计：每层施加一个跨 head/时间 bin 共享的系数；用上一完整去噪步的 50 层统计决定下一步；正常前两步与固定 .25 等价。KKT 求解、能量口径、节点克隆与生命周期检查均成立。初审发现的过旧计划来源防护已由作者修正，旧锚低信号的延迟回退口径已明确并补测试。最终冻结版 25 项 CPU 测试由独立审查进程全部重跑通过，10 个源码 SHA 在测试前后均与 READY 一致。无阻塞性代码问题，可交部署方准备单 pilot。

## 已核对的机制与边界

1. `budget.py` 的目标为最大化 Σ e_l u_l a_l，约束 Σ e_l a_l² ≤ .25²Σ e_l、0≤a_l≤.5。自由坐标 a_l=c u_l，达到 cap 后扣除其预算重新求 c，代码和 KKT 一致。无资格层保持 .25；零质量或正质量容量不足按明确退化规则处理，少用预算如实记录。
2. `attention.py` 在全部 50 层完成前不更新 anchors/layer_plan；完整步末记录当前统计并生成下一步计划。首个有效锚质量显式置 .5，质量相同时求解器逐元素返回 .25，所以正常前两个完整步骤均为 .25。各 run 新建 State，无跨 run 共享锚。
3. D=m(S−R) 和 O 都在输出投影 W_o 之前计量，e=‖D‖²/(‖O‖²+tiny) 仅覆盖选中输出 query。该约束不是 W_o 后、AdaLN gate 后或整个 DiT 的全局扰动预算。
4. 三个预算口径分别计算：上一度量下的计划系数、上一度量下的实际执行系数、当前度量下的实际漂移。当前 fallback 与能量漂移可以改变后两项；程序没有声称当前步精确守恒。
5. `nodes.py` 只读取原 positive 的参考元数据，不重写提示词/condition。启用时 clone MODEL，替换 50 个 block；已有 DiT/attention patch 会被拒绝。固定模式与原 H3Study mass-preserve .25 路径已有逐元素对照；禁用节点直接返回原 model。
6. 错序 block、未完成 forward、失败后复用和完整采样后复用均由状态机拒绝或不产生下一计划。事件窗口首尾统计被排除，引导仍应用于全部选中时刻。

## 审查发现及处置

### 已修正：计划来源未严格限定为紧邻前一步

初版 guard 仅要求 plan_source_forward < current_forward。CPU 反例把 current=2、source=0、plan_for=2，旧版本会接受该过旧计划。正常内部流程没有产生这种状态，但防护弱于文档承诺。作者已改为 source==current−1，并新增在 attention 调用前拒绝过旧来源的回归；独立重跑该回归通过，此问题关闭。

### 已澄清：当步局部回退和下一步锚资格是两个判据

当 A/B 相对初始锚同比缩小至 1e-10，但 raw probe 与 D²/O² 仍有效，当前层继续执行上一完整步的计划。独立 CPU 反例实际执行 alpha=0.209009483（requested=0.209009478），local_fallback=false，旧锚校准 fallback=true，下一步系数为 .25。这符合计划固定后的因果执行；不能把该条审计解释成“当步已执行 .25”。作者新增 raw_probe_evidence_valid、current_anchor_evidence_valid、next_plan_eligible 和 anchor_low_current_energy，明确区别并补回归。

### 非阻塞：性能字段仅涵盖各自计量范围

`statistics_transfer_bytes` 计的是 50×8 统计 buffer；逐层 `serial(pending)` 还会传输 alpha、head_energy、probe_indices 等审计张量。不能用 3200 字节代表整个审计的总传输量。`controller_gpu_dispatch_seconds` 使用 Python perf_counter，只是主机派发区间，不是同步测得的 GPU 时间。作者已在最终 DESIGN 中注明此口径。真实 pilot 应看完整采样时间，并保留现有统计同步/finish CPU 时间字段的限定。

### 部署交接检查

后续已独立比对两份 layer_pilots 实际图与 anchor_pilots 冻结图：只改变节点 14（输出路径）和 50（方法），其他节点逐项相等。模型链实际为 sampler10 → guider7 → timing52 → method50 → shift41 → loader1，positive 继续连接缓存节点 5。两例 prompt、seed、几何、参考缓存、sigmas、有效帧范围及对照输出保持配对；新节点已启用，end_frame 与 valid_frames−1 一致。图核查为静态接入检查，不启动推理。

- short_0252 graph SHA-256：`d72a024e2e5783bbf381427e3a3a829bc0eeef335bc42b8600a740c5c0c69507`
- short_0358 graph SHA-256：`5530cc72268d0e239716afded56347df39e5e32c91d321b829a2ef8c9bc298ee`

## 证据

初版 23 项 CPU 测试由独立审查进程重跑通过；另执行低锚信号与过旧计划两个 CPU 反例。全部使用 CUDA_VISIBLE_DEVICES 为空的独立临时目录，无模型推理、GPU、队列操作。作者补丁发生在审查过程中，最终版另行独立重跑 25 项 CPU 测试全部通过；测试前后均核对 10 个源码 SHA，未混用初版结果。

最终 READY：2026-10-23T04:01:13.095544+08:00。

- attention.py：`e9a2f8ee120421cfa66dd8e00b04e0fcaddcec89b9398fc497f7a297c051e79c`
- test_nodes.py：`280ee1f112d3cc79ebaa8ce97488f4db3ca5585bc557c6cccdeb55b361c20757`
- 完整文件清单和 SHA：同目录 READY.json。
- 实测视频效果与 GPU 性能留待受控 pilot；本审查不生成这两类结论。
