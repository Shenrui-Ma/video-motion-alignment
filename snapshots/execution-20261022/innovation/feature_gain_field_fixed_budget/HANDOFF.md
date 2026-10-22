# 固定剂量 field 控制器

CPU_VERIFIED_NOT_DEPLOYED / review_only。独立节点 H3TemporalGainFieldFixedBudget，默认关闭。没有修改原 field/线上节点/active manifest/报告。

原QP、A/B锚不变；只在当前solver_succeeded bins用完整分辨率能量确定共同倍率c，使ΣE clip(c*a,0,.5)²=.25²ΣE。固定/无证据/新锚/端点保持.25。无非零支持或支持容量不足时明确回退.25；日志不假称找到倍率解。

57 CPU单测及2图检查通过。真实wrapper20步×50层通过，14种审计失败注入全部拒绝。最大实际源dtype能量相对误差4.813e-8；CPU fixture实际α范围.180129–.309799。没有新视频，不声明效果。

4条待审图覆盖全部原始四案例，独立cohort fixed_budget_original_four，max_attempts1。只14/50变化，prompt/seed/cache/model/完整几何/sampler/QP保持。尚未发布，主线程独立审查后决定GPU。

只回收小JSON；真实9.6MB CPU fixture留.9临时目录 /tmp/h3_fixed_budget_cpu_20261023/fixture/budget_complete.json 供独立review，未下载本地。目录只含小源码/CPU证据，无模型或视频；review后可清理该专用目录。

检查入口：audit.py <actual_audit.json>；完整CPU入口：python -m feature_gain_field_fixed_budget.cpu_integration --out <isolated_dir>。需要CUDA_VISIBLE_DEVICES为空、CPU线程1，冻结core由H3_COVERAGE_FROZEN_ROOT指定。
