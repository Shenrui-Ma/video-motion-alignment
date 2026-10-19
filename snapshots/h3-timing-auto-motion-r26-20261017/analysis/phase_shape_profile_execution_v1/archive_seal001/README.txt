v1：已有63端点的离线重评分接口
2026-10-17

状态：已完成接口、10项合成正确性测试、68份输入metadata/hash检查。尚未执行任何真实63端点评分。准入由root单独绑定本目录FREEZE.json和候选v1的CODE/PROTOCOL freeze。

只读依赖与全部目标见BINDING.json。适配语义见ADAPTER_PROTOCOL.txt。科学内核及其31个合成结果保持已封存字节。

命令（每条为单一有界phase；attempt必须唯一）：
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_execution_v1/run_once.py check --attempt metadata_attempt002
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_execution_v1/run_once.py tests --attempt synthetic_attempt003
准入后：
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_execution_v1/run_once.py target --target-id r27_s05_bad1311_auto:000 --attempt target001_attempt001
全部63成功后：
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_execution_v1/run_once.py finalize --attempt finalize_attempt001

runner使用Mac共享锁，最多4线程，120秒单phase上限。BUSY返回75并保留收据；稍后以新attempt重试。技术失败保留error/traceback，不把技术错误转成科学UNKNOWN。提交点COMPLETE在最终SHA核验后原子创建；已完成目标不会重跑或覆写。

ROOT_TARGET_AUTHORIZATION.json的必要字段：authorized须JSON true，phase="target"，execution_freeze_sha256须本目录FREEZE的实际SHA；candidate_code_freeze_sha256=388850951becc46fbee2f06d536cc58dd2bfa5e771d43c4913436c2359028aa4；candidate_protocol_freeze_sha256=280f82dcd9a1db7cfe56d3640a6908ffc6d7287a7106af470b86d1b8ffe5e4d1；inputs_sha256=2386219d3264c320365dd8ce076310103d6085a37ff56b8a266cccb3b0e6f3fc；allowed_target_ids完整采用BINDING的63项。

输出：results/targets/<id>/attempt/RESULT.json、EVIDENCE.npz和目标目录COMPLETE.json。finalize汇总全部63项，保留各阈值common mask、raw/profile loss、UNKNOWN、候选计数、K与已选区间、耗时。semantic_accuracy和false_positive_rate留null。三条历史控制轨迹的20个端点各自相关；source07为两项final-only压力结果；另有一项source05final。全部已见输入仅用于开发诊断。

置信度>1为旧DWPose分数，本适配保持有限值原样进入v1最小权重，且对原关节坐标/分数做有限性检查。不能把这些分数解释为概率；也不等同旧R27的clip权重。
