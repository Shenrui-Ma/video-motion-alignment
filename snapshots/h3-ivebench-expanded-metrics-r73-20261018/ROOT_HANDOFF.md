R73 新五条 IVEBench：CPU 评测包

本地：/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018
.9：/data5/researcher/h3_runs/ivebench_expanded_metrics_r73_20261018
producer：/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018
Python：/home/researcher/miniconda3/envs/comfyui/bin/python

五条固定顺序与有效帧/生成总帧：0252 98/107；0344 58/73；0065 47/56；0135 112/124；0035 70/73。原片完整使用，画布1312×736，内容crop[16,8,1280,720]，24fps；有效前缀之外的末尾补齐帧统一排除。源在看新生成结果前已由官方元数据和源视频筛选。分母始终5。

数值继承：68个原R63/R64 runtime文件逐SHA保持，包括原官方IVEBench commit2dcf8900ee65197f43854c76f61c66a32bb8dbfc与CoTracker3 offline grid10/window60/query0/backwardFalse；官方MF计算未改。源与目标都fresh在.9、同Torch/CUDA/显卡型号。没有复用.41历史source tracks。原源SHA、完整输入映射、crop像素逐帧核验。

P1语义：configs/INPUT_PLAN.json按原字节继承producer；这是源预处理及原official edit_prompt的绑定。configs/SELECTED_5_MANIFEST.json保存官方源选择原件。configs/prompts/<source>.txt保存正式P1，prepare_pair逐字核 actualgraph，两臂完全相同。原edit_prompt仍显示为任务名称，P1含源/目标元数据和统一保持动作场景指令。

验证：本地31 CPU tests PASS，5条实际source tracker check-only PASS；.9实际31 CPU tests PASS。最终.9五源check-only和部署证据在audit/REMOTE9_CPU_DEPLOYMENT.json，结果拉回后本地归档。不启动tracker/GPU。CONSUMER_FREEZE.json冻结97项；SHA c4d2be6e60bbe3fef930ad61060f4a14dcc46c924d18545c7ff73683156fa700。

Root GPU入口

进入consumer根，优先最大有效112帧的short_0135，使用已准入空闲GPU的完整UUID：
 CUDA_VISIBLE_DEVICES=<root GPU UUID> PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python -u scripts/track_one.py --source short_0135 --method source --gpu-uuid <same UUID> --attempt 1 --control controls/short_0135_source_attempt1

脚本在CUDA前写ready.json，包含准确PID/UID/start/cmdSHA、输入manifestSHA和consumer freeze。root登记本次进程及peer后，把相同JSON写go.json。控制目录必须新建，脚本最多等600秒；两次freshNVML检查显存和own GPU union≤2，其他UID卡不计入。无需关闭同卡其他用户，只要实际余量达到门槛。初始free≥24GiB是112帧尚未实测的保守阈值，先记录实际peak再由root决定排程。现有checkpoint已实际SHA核验。每个source/target进程自然退出；root核exact释放。

其他源沿同入口各跑一次。Native/forced target在实际pair gate与READY后分别跑，参数相同、独立控制目录。source与target需同host及GPU型号；GPU UUID可以不同但软件/硬件型号必须匹配。大型PT/cache留producer，consumer只拉必需视频/JSON/score。

实际成片CPU消费

1. producer analysis/postrun/verify_pair.py --source <id> 由实际21组capture/noise/condition核gate；producer尚未完成时消费拒绝。
2. consumer scripts/collect_pair.py --source <id> --producer-root <producer>：校验r73 gate/P1、sameconditions/noise/prefix0..5、20Euler、Native0/forced450及各自长度；复制实际video/history/job/router/graph和gate。
3. CUDA_VISIBLE_DEVICES='' python scripts/prepare_pair.py --source <id>：全局CPU锁，验证actualhistory/graph与P1，制作有效crop，READY.json passed后交root target tracking。
4. root source/target tracks后，CUDA_VISIBLE_DEVICES='' python scripts/score_one.py --source <id> --method native（forced同理）。同host/runtime约束在包装层；原MF公式无变化。
5. 本地 scripts/render_pair.py --source <id>：三栏黑底中文caption，完整有效帧+前min(48,valid)帧，固定六时刻。source0065仅47帧，第二视图为完整47帧，避免造满2秒。
6. scripts/make_showcase.py --output <Downloads单文件HTML>：五条全留，全部五条有效才给完整均值。HUMAN_REVIEW单独记录编辑成功、动作保存；UNREVIEWED/PENDING不当成功，MF不当毫秒时延。

尚待实际：tracker GPU forward、真实target intake及端到端render。当前测试覆盖动态shape/物理时间、padding、源像素/映射改变、P0或跨源prompt、噪声/条件/prefix失败、旧gate、两卡上限、同host/runtime及固定5分母。所有GPU启动归root。
