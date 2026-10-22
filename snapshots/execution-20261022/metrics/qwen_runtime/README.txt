Qwen2.5-VL-72B-Instruct-AWQ / IS + CF CPU准备交接
日期：2026-10-22

位置
本地：/Users/researcher/DevProjects/video-motion-alignment/execution-20261022/metrics/qwen_runtime
远端：H3_SERVER:/data3/researcher/h3_metrics_20261022/qwen_runtime
权重：/data3/researcher/h3_metrics_20261022/weights/Qwen2.5-VL-72B-Instruct-AWQ
官方模型revision：c8b87d4b81f34b6a147577a310d7e75f0698f6c2
IVEBench commit：2dcf8900ee65197f43854c76f61c66a32bb8dbfc

完成范围
独立venv继承 /home/researcher/es/envs/comfyui 的只读包路径；新增包只安装在/data3。
PyTorch 2.5.1+cu121 / torchvision0.20.1+cu121 / Triton3.1.0复用，避免下载CUDA大包。
transformers4.51.3 / AutoAWQ0.2.9 / accelerate1.12.0 / qwen-vl-utils0.0.8。
所有tmp、HF/Torch/Triton/pip cache均在本目录。bin/ffmpeg仅链接现有ffmpeg7.1。
阿里云PyPI直连HTTP200；安装过程清除了HTTP(S)/ALL proxy，NO_PROXY=*。
pip check：No broken requirements found。CPU测试6项全部通过。
CUDA_VISIBLE_DEVICES=''且torch.cuda.is_initialized()==False；没有加载权重，没有启动GPU任务或后台服务。
完整checkpoint文件大小与已完成下载记录一致；43GB分片哈希验证沿用下载器记录，未重复读全权重。

实现边界
batch_eval.py默认仅CPU dry-run；必须显式--run才可能加载模型。
--run要求CUDA_VISIBLE_DEVICES恰好指定两张不同物理卡；nvidia-smi检查每张卡无任何compute进程且至少36000MiB空闲，否则加载前拒绝。
这属于启动瞬间准入检查，不构成跨用户GPU预约；启动负责人仍需安排空卡。
共享单个模型与processor，原版IS/CF类evaluate_video、压缩、prompt、1至5分解析以及single_video方法不改。
复制的官方文件运行时SHA256校验，免触发无关metrics包初始化。
使用官方自带compliance/fidelity qwen_vl_utils；当前自动选择现有decord。pip qwen-vl-utils仅作为兼容依赖，不替换自带代码。
模型加载使用torch_dtype='auto'（checkpoint配置bfloat16）、显式两卡map，禁止CPU/disk offload。
visual/embed_tokens和前40个decoder层在逻辑GPU0，其余40层、norm、lm_head在逻辑GPU1；max_memory记录为每卡36GiB。
该显式map是部署安排，36GiB参数不是运行时硬内存上限，首次加载需观察峰值。
AutoAWQ GEMM使用可导入的Triton后端，未安装autoawq-kernels扩展；其算子内部会转换float16，visual仍按checkpoint原精度加载。
结果evaluator包含模型ID、revision、完整quantization_config、实际dtype、device_map、包版本、GPU准入记录和original_precision_reproduction=false。
这是独立4bit AWQ评测配置；不标作FP16/BF16原精度复现，不合并成原精度结果。

CPU证据
CPU_VERIFICATION.json：import/config/processor、CUDA未初始化、权重文件大小、版本、pip check。
cpu_test.log：6项unittest，包括真实ffmpeg压缩和官方采样、真实processor张量输入、固定输出桩的结果封装。
cpu_preprocess_shapes.json：两项合成输入张量尺寸；测试分数4仅输出桩验证，不是模型评测分数。
official_source_sha256.json：官方源码副本哈希。
network_direct_check.txt / install.log / environment.freeze.txt：网络与环境证据。
dry_run.json：本次输入清单快照58条，.60已就绪58条，pending_inputs为空。这是阶段快照，不限制后续新增主实验和扩展实验。

接入现有metrics接口（由主代理决定并执行）
1. 从.81 /data/researcher/h3_metrics_20261022/ 同步metadata/和frames/到本目录staged/，使用原有统一有效帧及裁剪结果，不重新从原视频抽帧。
   原帧名保留%06d.png（实际prepare_frames.py产物）。batch_eval.py在TMPDIR中创建只读%05d软链接视图以满足官方格式；软链接目标为原始帧，保持数字编号、顺序与字节。两个官方函数仍按25fps重组并使用原压缩规则。
2. 将最新manifest.json复制到本目录manifest.input.json；其中jobs结构与现有metric_worker.py完全相同。
   --path-map只重定位metadata_file/source_frames_parent/target_frames_parent/video，不改metadata内容。
3. 保留.81 enabled_metrics.json，不在单卡轻量队列里启用72B。运行这个独立批处理入口。
4. 输出结构为evaluation_awq/results/<job_id>/<instruction_satisfaction|content_fidelity>.json。
   外层job_id/task_id/dataset/cohort/method/metric/status/score/detail与现有接口一致，另附独立evaluator配置。
   原始模型文本保存在detail.compliance_output或detail.fidelity_output。每项原子落盘，成功项重跑跳过；每次运行失败最多重试3次并留失败记录。
   此脚本是一轮批处理，不是自动监控服务；新增manifest后可由主调度再次调用。运行期间模型常驻，结束即释放。
5. 汇总时增加evaluator.configuration_id维度；可将AWQ补充列与9项数值指标/QA展示在同一任务表，但IS/CF须明确标注AWQ。
   不直接覆盖.81原精度pending_resource文件，也不把source基线当作已完成编辑。

准备启动命令（没有执行）
ssh H3_SERVER
cd /data3/researcher/h3_metrics_20261022/qwen_runtime
source env.sh
# 先dry-run，不加载GPU：
CUDA_VISIBLE_DEVICES='' python batch_eval.py --manifest manifest.input.json --output evaluation_awq --path-map /data/researcher/h3_metrics_20261022=/data3/researcher/h3_metrics_20261022/qwen_runtime/staged
# 两张GPU真正空闲并完成输入同步后，手动替换下列两个UUID：
CUDA_VISIBLE_DEVICES=GPU-EMPTY-UUID-0,GPU-EMPTY-UUID-1 python batch_eval.py --run --manifest manifest.input.json --output evaluation_awq --path-map /data/researcher/h3_metrics_20261022=/data3/researcher/h3_metrics_20261022/qwen_runtime/staged

重新CPU验证
source env.sh
CUDA_VISIBLE_DEVICES='' python -m pip check
CUDA_VISIBLE_DEVICES='' python test_runtime.py
CUDA_VISIBLE_DEVICES='' python inspect_cpu.py

剩余验证
两张空卡、实际AWQ Triton CUDA kernel、完整72B加载峰值、真实IS/CF生成尚待GPU阶段。
AutoAWQ0.2.9的维护者最后测试组合是Torch2.6.0 + transformers4.51.3；本环境复用Torch2.5.1，当前CPU导入/处理器和依赖检查通过，CUDA兼容性需首个真实batch确认。
本venv有继承包路径，原comfyui环境未来升级可能改变复用版本；上线前比对environment.freeze.txt和constraints.txt。
不自动调小采样、max_new_tokens、视觉分辨率或换模型来规避OOM；若资源不足由负责人重新安排GPU。

官方参考
https://huggingface.co/Qwen/Qwen2.5-VL-72B-Instruct-AWQ
https://raw.githubusercontent.com/casper-hansen/AutoAWQ/v0.2.9/setup.py
https://raw.githubusercontent.com/huggingface/transformers/v4.51.3/src/transformers/quantizers/quantizer_awq.py

追加：统一帧快照同步
本地运行 python sync_inputs.py。仅在qwen_runtime/写清单、日志，在.60的qwen_runtime/staged写输入文件。
源.81不写文件；两路SSH连接使用172.18.32.81和172.18.33.60，不设置ProxyCommand/ProxyJump，清除代理变量。
传输通过Mac进程内存管道，Mac不落媒体文件。只选择已有PREPARED.json且数量匹配的发布目录，排除.partial构建目录。
源快照逐文件SHA256，接收端写.qwen-sync-partial，SHA256匹配再原子替换；结束后再校验全部目标文件。
重复运行重新拍摄源快照，SHA256匹配的目标文件跳过传输；不会删除目标已有文件。失败重跑可继续。
清单在传输前从最新../manifest.json复制；完成后才发布到远端manifest.input.json。增长中的新任务留给下次同步。
sync_runs/<时间>/source_snapshot.json、manifest.input.json、destination_before.json、destination_after.json、transfer.log和SYNC_RESULT.json保存本次完整证据。
CPU dry-run在统一帧包含PREPARED.json且帧数与job一致时才判定就绪，避免误用正在同步的目录。
python validate_staged.py --exercise会核对清单元数据、receipt、帧编号和目标视频SHA，再对一条真实source/edit输入执行官方CPU预处理；生成输出是固定测试桩，不保存为评测分数。

2026-10-22 本次输入同步结果
源快照包含58个帧集、5593张PNG、58份PREPARED.json、9份metadata JSON，共5660文件、5,527,275,668 bytes。
目标每个文件接收时SHA256核对后原子发布，并在全部传完后再次读取核对；5660/5660通过。Mac仅保留小型清单与日志。
manifest SHA256: 7d641972d973801c81e189e49c6d2f79ceace43dbe9adeea8888a54c4f2787d8。
覆盖main的9个task、58条job：IVEBench56、FlexiAct2；source9/native9/fixed8/early8/late8/split8/global_weak8。
全部job ID见SYNC_RESULT.json，逐文件原始摘要见sync_runs/20261022-043630/source_snapshot.json。
没有启动GPU模型或评测服务；实际IS/CF结果仍待两张空闲GPU。
