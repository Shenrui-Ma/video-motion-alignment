v2方向用途候选：操作与产物

PROTOCOL_FREEZE在实现与科学运行前创建，CODE_FREEZE在任何observer评分前绑定7个源码/输入清单。科学输入固定43项：原31完全保留输入hash与原真值，新12使用连续单调解析warp。每条case在同一输入上运行冻结v1与v2，保存paired输出和真值数组。

使用已有 .venv-current/bin/python，run_once.py tests/case/finalize；每次指定唯一--attempt，case附--case-id。每phase共享Mac锁、最多4线程、120秒上限；BUSY75稍后以新attempt退让。科学验收fail保存到RESULT，case执行成功不代表科学通过。全部43完整跑完后finalize才写SUMMARY。

CASE_MANIFEST保存source/target/truth逐数组hash，原31源/目标hash与旧清单一致。results/<case>/<attempt>/RESULT.json保留case、v1/v2结果、原point任务与新direction任务。local12另存每段plateau覆盖、转接区逐帧连续相位、所选窗口方向比例和旧草案point误差诊断。EVIDENCE.npz保留两方案全区间profile、mask、J/拒判等，v2保留完整相位集合拓扑；truth__前缀是解析真值。

本scope只含合成评分，未新增真实63评分，也不调用视频推理或在线控制。D为固定工程容忍度集合，方向判定并不形成误差覆盖概率或闭环稳定性保证。
