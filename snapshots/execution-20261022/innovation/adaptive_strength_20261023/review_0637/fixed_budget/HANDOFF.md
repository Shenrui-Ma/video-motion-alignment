# Fixed-budget collector 接入完成

已接入 h3-temporal-gain-field-fixed-budget-v1 / gain_field_fixed_budget。独立审计复制到 batch/fixed_budget_audit.py 与 fixed_budget_field_audit_base.py，仅修改相邻导入文件名。实际alpha、candidate_alpha、完整bin_energy、fixed_budget径向解/剂量日志分开保存；fallback_layer_fraction引用实际预算回退。记录完成层可以实时检查，只有完整审计、匹配result/attempt及SHA验证媒体齐备才标verified。

科学plan直接读取 innovation/feature_gain_field_fixed_budget/pilots/jobs.json；没有另建重复batch plan。根据三个activated TARGET_RECEIPT原子替换收集配置，24计划中旧20条job和owner全部保持。新四条：.41手帕；.81饮酒→机舱；.9书本。远端队列由资源代理管理，本接入只读。

验证：原37+新增7=44 CPU回归通过；真实20×50 CPUwrapper文件在远端原地重放，1000曲线点、950层candidate与applied不同完整保留，live0issues、complete audit通过；故意改预算被拒。测试用synthetic结果/媒体封装，与真实生成视频区分。五个代码文件AST通过，冻结audit基底按字节一致。

已执行一次真实collector与paired汇总：19 verified / 3 in_progress / 1 pending / 1 research_hold / 0 attention_required，来源错误0，310条真实评测记录。新四例尚未标完成；原2与扩展2均保留0/2，完整与部分均值皆null。45个输入SHA通过，368行CSV。原19条结果继续保留。

证据：COLLECTOR_OWNERSHIP.json、COLLECTOR_CODE_EVIDENCE.json、COLLECTOR_CPU_INTEGRATION.json、COLLECTOR_ACTUAL_CHECK.json。最新快照已释放给主线程重建报告；不包含新的效果主张。
