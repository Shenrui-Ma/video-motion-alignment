R100：两条基础编辑修复，Native-first；CPU准备，GPU由root启动

本地 /Users/researcher/DevProjects/h3-timing-ive-task-repair-r100-20261019
远端 /data5/researcher/h3_runs/timing_ive_task_repair_r100_20261019
.9 GPU0 / GPU-REDACTED / port8564 / UID1016。
normal、reserve8、初始空闲门40960MiB，max2张自有CUDA卡；实际启动前等待R97原PID和CUDA精确释放。其他用户进程可同卡且有足够余量。

两源固定顺序
1 short_0114：Replace the basketball with a neon-lit ball。完整原片109帧25fps，映射105有效帧24fps，补至107。R91既定P1文字、原始和准备视频/provenance逐字复用；全部原数值不变，只改root/run标识。
2 short_0392：Remove the ornate fireplace。完整原片56帧24000/1001fps，映射57有效帧24fps，补至73。R64原始和准备视频/provenance逐字复用。新六段P1明确删除整个雕花壁炉、mantel和支撑外框，局部背景填充；保留人物白套装、手势顺序/时间、原房间其余部分与镜头。
每个case只有Video1，无Picture条件。两条各fresh Native；root确认基础编辑完成后可补同进程、同条件、同原始AV噪声的fixed。

科学配置
20Euler、CFG1、无Turbo；video12/audio3 sigma原数组；alpha1，50层，steps6..14。六个数值文件字节与R92/R91相同。Native/forced仅attention mode与审计run标识不同。前6次AV预测、6种真实条件blob、原始AV噪声必须实际exact。
0114最后时间bin包含2帧padding；0392只干预与57有效帧相交的18个bin，其最后bin56..59含3帧padding，后4个纯padding bin保持原计算。评测排除padding，crop16,8,1280,720。
未导入.41 float解码SHA作为.9期望；正式门比较实际同.9两臂条件。

启动命令（root确认资源及R97释放后）
cd /data5/researcher/h3_runs/timing_ive_task_repair_r100_20261019
nohup python3 -u audit/root_run_batch.py --execute --attempt root_task_repair_attempt1 --peer-root /data5/researcher/h3_runs/timing_flexiact_character_repair_r98_20261019 > audit/root_task_repair_attempt1_wrapper.log 2>&1 < /dev/null &
peer-root必须按当时实际仍活的另一张卡任务根填写；该路径来自R98实际runtime；root仍须核对当时是否活跃，已结束peer会被过滤。GPU服务由wrapper精确登记；现有admission.ready_for_launch=false。

Native完成后
controller自己运行CPU NATIVE_RUNTIME_GATE，状态awaiting_native_review；绝不直接提交forced。root实际看任务完成和动作，再做一次原子决定：
python3 scripts/execution_gate.py decide --root-reviewed --source short_0114 --choice guide --reason '已核霓虹球编辑完成，补固定时序引导对照'
或 --choice skip --reason '具体基础编辑失败或跳过原因'
0392以相同方式审阅。决定绑定实际Native gate、视频/条件/noise/graph/history SHA和原服务PID/UID/start/cmd；条件变更或换服务代次拒绝后续forced。
第一次实际guide后状态awaiting_first_guided_review，root看真正pair，再：
python3 scripts/execution_gate.py review-first-guided --root-reviewed
首源skip时，首guided审阅顺延至下一实际guide。skip保留Native-only，不制造对照。
每次待审1800秒，单job10800秒、服务总57600秒；HTTP不可读为UNKNOWN，原期限继续，POST不重发。超时/失败按原精确身份清理服务。

验证与范围
104项本机CPU回归通过，含Native前禁止guided、guide/skip/首guidedreview、已变服务/媒体/noise拒绝、同图数值和0114R91逐字段一致、mock实际condition/noise/prefix篡改拒绝、HTTPUNKNOWN及生命周期。
实际本机两原片与prepared PTS已核；实际.9被动测试见audit/TARGET_CPU_VERIFIED.json（成功后为准）。旧R91/R64/R92全部保持原样。
audit/SCIENTIFIC_DIFF.json、audit/INHERITED_BYTE_BINDINGS.json记录继承与差异；prompt是完整表达包，修复成功也不能归因单个格式标记。本批支持任务修复和既有固定引导检查，无新架构声明。
