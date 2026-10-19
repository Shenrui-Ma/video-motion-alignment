同部位相位分段的独立 CPU 原型

位置：/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_consistent_segmentation_execution/
设计冻结：../phase_consistent_segmentation_design/FREEZE.json
设计 FREEZE SHA256：1cea183950477d773a6297169ef8b77fd3a0b65cddc73feafc3cc64e37943119
INPUTS SHA256：2386219d3264c320365dd8ce076310103d6085a37ff56b8a266cccb3b0e6f3fc

本交付只完成实现、合成测试与 metadata/SHA 检查。真实源视图校准、63 个目标 pose 评分及 GPU 接入均待主 agent 审查后的对应授权。原 source_anchor_selection_execution 的公式、代码、结果均未改。

文件职责
segmentation.py：两臂独立、可变区间 DP，null±2 共同支持，缺失下界，复杂度代价，有限相位竞争，覆盖/持续性统计。
run_once.py：一次有界 phase、共享锁、只读输入校验、授权检查、不可覆盖结果、提交前 SHA 复核和原子 COMPLETE。
vendor/：从先前冻结实现逐字复制的 pose 特征与物理帧匹配两个模块。
tests/test_segmentation.py：解析单位向量、DP 穷举、遮挡、phase 歧义、授权和中断负例；另输出零尺度相关扰动压力结果。
OUTPUT_SEMANTICS_ADDENDUM.txt：标签解释、严格相位拒判、lambda=0 和最新用户目标。

执行环境
PY=/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python
SCRIPT=/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_consistent_segmentation_execution/run_once.py

所有命令形态为：
  <PY> <SCRIPT> check --attempt metadata_attemptNNN
  <PY> <SCRIPT> tests --attempt synthetic_attemptNNN
  <PY> <SCRIPT> calibration --attempt calibration_attemptNNN
  <PY> <SCRIPT> target --attempt endpoint_attemptNNN --target-id <INPUTS中的完整id>
  <PY> <SCRIPT> finalize --attempt finalize_attemptNNN

每个 attempt 必须独有。phase 最多 120 秒，最多 4 线程，共享
/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock
busy 写收据并退出 75。调用结束释放 CPU 锁。每个目标单独调用，不含常驻调度；科学结果写在 results，执行证据写在 audit。未安装依赖、未启动 GPU、未提取新 pose。

授权结构（由主 agent 创建）
ROOT_CALIBRATION_AUTHORIZATION.json：
  authorized: literal true
  phase: calibration
  execution_freeze_sha256: 当前本目录 FREEZE.json 的 SHA
  design_freeze_sha256: 上述设计 SHA
  inputs_sha256: 上述 INPUTS SHA

ROOT_TARGET_AUTHORIZATION.json：
  authorized: literal true
  phase: target
  execution_freeze_sha256 / design_freeze_sha256 / inputs_sha256: 同上
  calibration_sha256: 审查后的 CALIBRATION.json SHA
  allowed_target_ids: 授权评分的 INPUTS target id 列表

target 会验证校准 COMPLETE 的全部产物，finalize 要求 63 个 target 全部完成并都得到授权。每次真实 phase 开始检查绑定输入的 SHA 和 141 帧/24 fps/time_s=i/24 网格。完成提交前复核该 phase 使用的代码、输入、授权和校准 SHA。COMPLETE 用同目录临时文件+fsync+硬链接独占提交，避免存在但只写一半的完成标记；已有坏标记显式报错。失败 attempt 保留，下一次使用新 attempt id。

数值范围
3 条历史轨迹各 20 个端点，另加 R37 最终成片与 source07 两个父成片，共 63 项。source07 当前没有完整轨迹，显著标为 final-only。source05 的六个有序不同源视图对一次校准 lambda，迁移到另外两个 source 时原样保留，并记录迁移身份。
EVIDENCE.npz 保留逐槽证据/mask/weight、每个区间的 reward 和 feasible，RESULT.json 保留全部选中窗口及每个远 lag 的竞争记录，包括拒判。DP 拒判后无次优回退。

已知限制
源视图经验尺度不能保证生成端点错误率。相关几何扰动即使真实时间 warp=0，也可能看起来更接近某个非零相位。lambda=0 的固定八项合成压力例产生了相位候选，详见最终 test receipt 绑定的 stress JSON；这是原型的已知混淆，不是实际源校准后的误触率。单元测试验证实现和边界行为，不能替代这一科学限制。
UNKNOWN=-1 及“任一远 lag 缺支持即拒判”可能让真实样例全部拒判；本轮不为迎合结果更改规则。保留 NO_SUPPORTED_PHASE_DEVIATION 的原协议兼容字段，同时输出 NOT_SELECTED_BY_OBJECTIVE、正值候选数量及 selected-but-UNKNOWN；这些都不等于语义正确。
观察器 A 与执行器 S 分离。本原型没有证明动作时间错位的因果来源，也没有实现 H3 自动干预。后续目标是在多个独立视频上相对 Native 改善并接近人工选窗结果。

原186/扩展279/源Q的历史比较继续引用之前封存结果；本目录不会改写旧扫描或将 24 帧长度伪装成原扫描。finalize 的覆盖/持续性属于本候选及两项机制消融，跨方法语义效果需主 agent 结合历史资料和独立视频检查。
