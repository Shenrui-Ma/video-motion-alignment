# R13 retry3 独立验收与单步分叉结果

正式运行 `r13_s05_one_step_fork` 已成功，完整 CPU 验收通过。这是历史 Full 轨迹上的三个预选单步分叉诊断，**没有生成新的完整视频，也没有新增独立 pose 结论**。此前失败尝试保留在原审计目录，不计为科学失败或本次六次预测。

## 完整性与资源释放

实际成功 history 的 prompt 为 `16ffa0e5-065d-4661-9e2a-cac5d88bb24f`。本轮恰有6次模型预测、300个 block 调用、0路由、0 sampler callback、0 sampler trajectory update；用 Euler 公式构造6个候选缓冲区仍包含数学计算，不能写作“零计算”。pairs 恰为 `[6,10,14]`，各自评估下一索引7/11/15。本文索引均为 zero-based。

官方 `scripts/verify_fork.py` 和独立检查均通过。实际目录恰有12个不同 `.pt` 文件：6个候选输入和6个端点。逐文件核验SHA、FP32 dtype、形状、有限性、metadata、两流归一化和重新打包完全一致。三组 Full 更新候选与历史下一步实际输入SHA相等；随后原生预测的 video/audio 张量与历史下一步端点逐位相等。

六次实际输出头记录均为 `single_linear`、`pdd_active=false`、`bank_size=1`、`start=null`、`stop=null`；完整21点 FP32 grid、物理索引、video/audio shift12/3均核验。审计字段仍叫 `pdd` 不代表真实使用了多专家 PDD。实际头部 sigma 与原 grid 可有不到1e-6的计算舍入差，未将其误写为所有浮点字段逐位一致。全局 RNG 和候选输入未被预测修改。

epoch1792151204 的 live 检查确认 service44923、supervisor44888、watchdog45514、controller45515 全不存在；精确 cleanup_44923 记录 own_compute_absent=true，GPU2 UUID `GPU-REDACTED` 为8MiB/0%、无 compute。随后已通知主控启动下一任务；该释放证据只描述当时状态，不能要求后续 R14 运行时继续空闲。

## 单步结果

从同一个历史状态 x_n 分别用 Full/native 的预测构造 U_F/U_N，再对二者都运行**下一步的原生模型**。下表不是“下一步继续Full”对比“下一步native”。所有内部读数均通过既有 gap5 观察器的拒判门，窗口固定50–65。

| 历史索引n → 读取索引m | Full更新后的下一步原生读数 | native更新后的下一步原生读数 | 差值 |
|---|---:|---:|---:|
| 6 → 7 | +6 | +10 | 4帧 |
| 10 → 11 | +1 | +2 | 1帧 |
| 14 → 15 | 0 | 0 | 0帧 |

这支持：在本病例的早期索引6，一次 Full 选择确实改变了下一步原生预测，内部相位收益不只存在于当次被引导端点；但下一步仍残留+6，不能说一次纠正已被完整保存。索引10的差异较小，索引14两路粗读数相同；读数相同不等于张量相同，也不等于末期干预对最终细节无作用。三个位置来自同一历史轨迹，不是三个独立样本。

## n10 与 R12 的实测桥接

R10/R12 在Full索引6–9的实际输入及端点签名一致，native索引10的输入和 video/audio 端点也一致。本次又验证了实际保存的 R12 raw input10 与 R10 input10 张量逐位相等；原生10两流端点实际张量相等。

R13 的 `n10_u_native_raw.pt` 对应输入SHA为 `29c9f7c6271f5ae3dd3ab023a2c3e106a84486bec4cd1668c863908287daa3cf`，与 R12 实际 native11 模型输入记录相同；`n10_fork_native_endpoint.pt` 的 video/audio 实际张量与 R12 `step011_native.pt` 逐位相等。R12 没有单独保存 input11 原始张量，因此输入门是“R13实际候选缓冲区对 R12实际模型输入SHA”，不能写成“两份存盘 input11 张量比较”。端点则确实进行了两份文件的 SHA 和实际张量比较。

条件完整SHA不同，递归核验仅两叶不同：`original.positive[0].uuid` 与 `processed.positive[0].uuid`。其余完整条件树相等，不能删除任意其他条件差异。R13复原R10 UUID；本次端点逐位相同实证支持这个特定 UUID 差异未影响该预测。该桥接严格限于n10：n14此前轨迹已经不同，不扩展到R12后续所有步。

结合 R12 已有独立 pose（首次OFF索引10方向/腕均+4，索引15及final方向+3、腕+4），目前证据更符合“停止时已有残留，粗观察器读数偏小”，不支持“已独立证实完全对齐，然后停止导致新增回退”。R13 不决定最终最佳策略，也不替代完整视频评价。

## 时间与归档

6 NFE；完整history542.929秒（包含非fork准备）；fork wall458.989秒，模型同步计时438.878秒，条件hash8.651秒，端点归档加内部读出7.539秒，候选输入归档1.187秒，候选构造0.00115秒。归档与observer计时是合并字段，不能拆成虚构的纯observer成本。CPU完整验收5.127秒。仅记录效率，不据此追加速度实验。

关键证据49文件已下载并逐SHA核验：`archive_manifest.json`；压缩包SHA `6d78555fbecaa67ca92288040428492b9d4e95a7f9e4cbfc4049686ccd8fa4aa`。12个大张量保留于远程，完整路径/文件SHA/张量SHA/metadata/finite结果见 `archive/analysis/pose/complete_integrity_gate.json`。官方结果见 `archive/analysis/verified_fork.json`，简表见 `compact_summary.json`。

补充实际部署检查：90个冻结文件的远程当前SHA全部符合bundle_manifest；见 `deployed_bundle_gate.json`（manifest SHA `55a366673b2f9bdc4e3a2a909724b1d4b850320adf9addd2d0e95df2cac0dab9`）。此为原49文件归档之后的独立补件。

本次仅新增分析验收脚本与证据文件，未改运行配置、算子、协议、观察器阈值，也未启动模型或重启失败任务。没有新颖性或泛化结论。
