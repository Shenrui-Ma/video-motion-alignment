# R65 FlexiAct 成对评估与展示

独立目录：`/Users/researcher/DevProjects/h3-flexiact-forced-metrics-r65-20261018`。

已部署 .41：`/data3/researcher/h3_runs/flexiact_forced_metrics_r65_20261018`。原 .41 `/data3/researcher/ComfyUI/.venv/bin/python` 已通过旧CoTracker的CPU导入和checkpoint加载：24,149,859参数全部CPU，torch2.11.0、CUDA未初始化、模型forward0。未安装或升级共享包。实际证据为audit/HOST41_CPU_COMPATIBILITY_1.json。

官方MF沿原FlexiAct配置：CoTracker stride4/window8，grid55、mask=None，作者的完整位移方向余弦公式与对角线减1/每行最大值保持原文件。56个冻结依赖文件及checkpoint共98.1MB，原RUNTIME_FREEZE SHA `fa573e2065d1c140ef232513d73b909d2aa2902046d4a9becf609a6e549ad580`。

本批在.41新追踪两条source和四条新Native/ON输出，统一Torch、CUDA与GPU型号，实际UUID逐条记录。可在R65首对完成后通过ComfyUI `/free` 卸载模型，保留服务上下文，再在该卡顺序评分。R49历史source tracks原字节保留在reference_cache_r49，仅作历史参照。R49实测峰值reserved约36.66GiB；独立`track_shared.py`只替换资源准入：实际空闲至少40GiB、温度低于85°C、自己涉及最多两张GPU。允许其他用户及已卸载ComfyUI的同卡上下文；每次追踪前记录实际free、进程UID/UUID，原tracker记录实际峰值显存。所有官方数值文件保持原SHA。root完成实际资源核验后调度。准备agent未启动GPU。

## 1. 先提取两条source轨迹

在.41目录下：

`python3 scripts/tracking_plan.py --source fitness --method reference`

命令只返回argv/shell与root准入说明。root启动该命令后，独立资源wrapper会写`controls/reference_fitness/ready.json`并等待。root核对PID/UID/start_ticks/cmdline_SHA并登记peer资源，再把原样ready.json原子复制为go.json。进程完成并确认显存释放后，对one_leg重复。保存结果为`tracks/reference/<source>/{REPORT.json,tracks.pt}`。

## 2. 收到完整成对结果后发布严格49帧输入

首先在producer完成CPU实际成对核验，得到passed的PAIR_RUNTIME_GATE.json。随后在.41消费目录执行：

`python3 scripts/collect_pair.py --producer-root /data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018 --source fitness`

`CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/prepare_pair.py --source fitness`

collect仅复制真实两条成片、成对receipt和job/history/router/graph，小于原全部x0数据。prepare保留full158，直接调用原R49 release49.py：取0,3,6,…,144，共49帧@8fps；分辨率1152×768，无裁剪。lossless编码后逐帧MD5验证，路径/物理时间/原source SHA通过原run_tracks.validate_generated_binding。源视频按原官方720×480输入；作者tracker自行使用其原实现，未自行改尺寸或grid。

## 3. 新Native/ON追踪与MF评分

`python3 scripts/tracking_plan.py --source fitness --method native`

`python3 scripts/tracking_plan.py --source fitness --method forced`

root逐条执行预CUDA登记流程。生成`tracks/native/fitness`与`tracks/forced/fitness`。随后：

`CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/score_one.py --source fitness --method native`

`CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python scripts/score_one.py --source fitness --method forced`

one_leg相同。score_one要求fresh source/target的Torch、CUDA版本、GPU型号与host、checkpoint、vendor、grid等一致，之后调用原score_pair.py。undefined原公式结果保留原状态。MF不直接表示毫秒延后，需结合下述时序和编辑结果。

## 4. 物理时序：复用.9原CPU DWPose

把本独立消费目录同步到`/data5/researcher/h3_runs/flexiact_forced_metrics_r65_20261018`，包括incoming和静态runtime、source_pose、inputs即可；`.9`部分不需要fresh MF轨迹。CPU脚本只对incoming里的full158生成新DWPose，复用已有准确source158姿态缓存。参数、模型及代码SHA、四线程、158帧、joint顺序和完整provenance全部与原source核对。

`CUDA_VISIBLE_DEVICES='' /home/researcher/miniconda3/envs/comfyui/bin/python scripts/run_pose.py --source fitness --method native`

`CUDA_VISIBLE_DEVICES='' /home/researcher/miniconda3/envs/comfyui/bin/python scripts/run_pose.py --source fitness --method forced`

`CUDA_VISIBLE_DEVICES='' /home/researcher/miniconda3/envs/comfyui/bin/python scripts/evaluate_physical.py --source fitness`

one_leg相同。共同CPU consumer.lock串行，不自动启动或修改在线observer。数值模块保持原FREEZE `59665ac9…`，同时报告原四个固定时间范围、三种手臂特征、0.3/0.5置信度，125ms采样，保留UNKNOWN。原evaluator第二方法参数名automatic在输出中仅映射为forced，计算未变。

fitness/one_leg是原固定5里按已知Native延后与编辑成功选出的development子集。前2秒view为原49点的0…15，对应原观察250–375ms延后。one_leg的抬腿部位超出部分成片，现有物理结论只涵盖可见手臂。

## 5. 三横拼视频

Mac复制incoming后运行，或提供服务器可用中文字体：

`python3 scripts/make_triptych.py --source fitness`

输出first2seconds（0…47物理帧）和full_valid（0…146）两个三列视频；相同物理帧横排，原尺寸1152×768，每列下方黑边caption：参考视频、编辑后视频、编辑＋时序引导后视频。第一列黑边左侧注明角色替换。

`python3 scripts/make_showcase.py --video showcase/fitness_first2seconds.mp4 --video showcase/one_leg_first2seconds.mp4 --output showcase/R65_两例前两秒_单文件.html`

HTML内嵌实际视频，只有已完成视频才能加入。未生成时不会输出占位结果或虚构成绩。

## 验证

原本地与.41各6项轻量接口测试通过；另增加共享显存与root登记门的8项CPU测试：实际pair必需、原49采样、allOFF/错NFE拒绝、条件等价检查不可缺、原runtime字节、方法标签映射保留数值。已核验冻结源缓存与依赖SHA；原数值工具未重新设计或大规模重测。暂无R65实际生成轨迹或评分。

资源wrapper与官方tracker在同一进程内执行，官方`run_tracks.py`的两次pre-CUDA资源检查调用新资源门。`tracking_plan.py --gpu-uuid GPU-REDACTED`可指定R65使用的GPU1；默认仍指向GPU2。root按实时余量选择。同卡其他进程的出现不触发终止；实际OOM由官方runner写失败receipt并退出。
