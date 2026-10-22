H3 semantic clock 2×2 — STAGED ONLY / 2026-10-16

未部署、未加载模型、未运行 GPU。本包仅准备：新增独立自定义节点、编码验收图、B/C/D 三张完整图、CPU 契约测试。
主方法假设见 ../literature/semantic_sampling_hypothesis.txt；运行边界见 ../analysis/semantic_clock_runtime_plan.txt。

固定条件
  A = P0/T0：复用 full seed1 native，新增 A0 仅重算编码以验收新节点。
  B = P6/T6：视觉采样 [6,18,…138]，按这些时刻给标签。
  C = P0/T6：视觉采样 [0,12,…132]，给 P6 的标签；人为元数据不一致探针。
  D = P6/T0：P6 图片配 P0 标签；人为元数据不一致探针。
  P6 物理偏移 6/24=0.25 秒；一位小数显示标签 T0=.2/1.2/…，T6=.5/1.5/…，差 0.3 秒。
  所有组 2 fps、12张图、6双帧视觉块；完整 dense VAE 141帧/42bins 不变；未修改注意力。
  同 seed2026101311、Euler20、shift12/3、原提示词、模型、几何1312×736、24fps、native router。

文件与入口
  extensions/H3SemanticClock/__init__.py：真正替换 clip.tokenize 的 minimax_ref_items 输入。
  extensions/H3SemanticClock/audited_event.py：原 EventAudit 完整逐字拷贝；只复用 Store/VAEProxy/CachedNoise/sampling_plan 等工具。
    该拷贝不是独立加载的 custom-node 包，不注册其旧 NODE_CLASS_MAPPINGS。
    真正导出的只有 H3SemanticClockReference / H3SemanticClockNoise / H3SemanticClockGate。
    所有可达写目录均由新 task_path 检查 exact resolved descendant semantic0，旧 module 的 audit_root 不会调用。
  configs/s05_semantic_a0_encode_gate.json：终端 node99 H3SemanticClockGate；没有 UNETLoader、SamplerCustomAdvanced、VAEDecode/SaveVideo。
    只用 CLIP/VAE/原图视频输入，真实运行 native preprocessing、Qwen50层编码，并生成/核对 paired noise。
  configs/s05_semantic_{b_p6_t6,c_p0_t6,d_p6_t0}.json：完整20步图。node51从99取 positive/target，采样必依赖验收。
  baseline/：复制原始 conditioning/noise JSON（字节不变）；不用复制其 tensor_blobs，比较的是实际 tensor 哈希。
  scripts/check_encoded_acceptance.py：只读核对已编码记录，跨组检查相同P的实际视觉图片哈希一致、相同T的timestamps一致。

运行时零值门
  1. 必须先运行 A0；默认 P0/T0 仍把 native 原 item/list/tensor 对象送给 tokenizer。
  2. 对真实最终 conditioning embedding、原始 token ledger、expanded tags、position_ids、dense prepared frames/latent
     与 baseline JSON 的 shape/dtype/SHA 做精确相等，不只检查口头 6960/87592。
  3. 对所有组，expanded token count、token类型/权重/视觉块位置、tag哈希、完整 layout/position哈希必须一致。
     同位置 ref/target 原生坐标差还逐行验证为235，不做原点对齐。
  4. A0 node99 调用实际 CachedNoise.generate_noise，对视频/音频流 SHA 与原始 native noise audit 精确相等。
     通过后写 audit/s05_semantic_a0_p0_t0_condition_zero_gate.json，含 baseline+实现哈希和 accepted condition hash。
  5. B/C/D 在编码前检查该许可；每组 own condition_run_id，避免不同条件图缓存错用。
     编码后每组必须再次通过全部布局/dense/实际noise门，才可进入 sampler。
  6. 非零组的最终 hidden states 允许且预期不同，不要求 embedding SHA 相同；其他指定不变量不得改变。
     任何 token数量/标签/位置变化都拒绝，不重复token、不重标位置、不放宽精度来凑等价。

CPU 验证
  PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' \
    /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python \
    semantic_clock_staged/tests/test_semantic_clock.py
  audit/cpu_tests.txt：16 tests passed。
  测试运行冻结源码 AST 的 native execute、tokenizer 分块循环、process_video_block、PackedLayout。
  模型权重/词表/resize后端用明确stub；不声称通过了真实Qwen权重零值门。
  真正 full geometry PackedLayout 的87592×3位置张量与已归档SHA相同，CPU可直接确认。
  GPU A0 验收尚未执行；不会在此包准备阶段假称已通过。

部署限制
  候选 remote root = /data5/researcher/h3_runs/timing_autoresearch_20261016_semantic0
  候选 GPU0 UUID = GPU-REDACTED；port8462。
  必须等待 transfer0 全队列结束、CPU inventory/cleanup完成、owned process/VRAM释放后，由root做独立review/admission。
  primary可能仍运行。不可覆写它的代码、服务或队列，不得复用旧prepare_runtime.py。
  本包没有启动/部署脚本；现有安全coordinator需由root针对新实例明确准备，不能简单重跑transfer实例。

冻结前审查修正：Reference/Gate IS_CHANGED=NaN 强制实时门；A0 Gate每次先撤销旧许可，错误噪声不留下旧passed许可。
baseline两JSON的原始SHA已固定在源码，GuardedNoise每次生成再次核验实时许可/条件/噪声。
实际native tokenizer做6–12次纯文本词法探针，验证六段timestamp BPE长度与内容、其他文字IDs逐项不变；这些调用不执行Qwen。
后验checker使用显式ValueError，不受python -O影响，并核对磁盘baseline/extension SHA及每块视觉像素哈希。
所有配置filename/run_id均已统一小写，兼容当前job.validate_name。
