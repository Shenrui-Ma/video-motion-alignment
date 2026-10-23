# 参考编码内容与坐标校准：CPU 包

本包只完成候选 POLICY、CPU 输入构造、固定字典读出和合成反例。没有可用的真实模型 runner，没有读取真实 PT/NPZ，没有新增 GPU 前向或视频结果。`provenance.request_model_forward` 无条件抛出 `PendingRuntime`。

候选范围固定：short_0358 新同环境 native；step 9、19；layer 25；全部56 heads×8 query probes；31完整有效bins；内部[5,10)与[10,15)双射对换。保持目标AV x_n、sigma/schedule、位置/RoPE、角色、坐标条件noise、原Qwen3VL多模态presentation不动。原K_R字典对每步固定。最多2次新零扰动核验+2次对换前向仍未部署。

执行 CPU 测试：

```
/workspace/research-user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s /workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/innovation/signed_phase_calibration_20261023/content_coordinate_calibration_20261023 -p 'test_cpu.py' -v
```

32项通过。系统python3没有numpy；测试使用已有bundled runtime，无安装依赖。测试仅合成小数组与临时小NPZ，不触及真实捕获。

接口：

- `provenance.verify_sources`：所有来源SHA先通过；不写文件。`verify_original_native_states`从冻结policy取4份真实原state/QK文件SHA，但不解码PT。
- `provenance.verified_npz`：全部文件SHA通过后才解码精确成员清单，拒绝未知/缺少键、pickle和重复ZIP成员。纯CPU原语，未接真实captured PT→NPZ运行链。
- `core.construct_frozen_inputs`：对参考latent做唯一置换，所有冻结输入各自copy，无别名；坐标noise不换。`coordinate_augmented_rows`是与原公式一致的NumPy FP32候选，尚待未来Torch/rawAV/QK实际核验。
- `core.fixed_dictionary_readout`：没有new-K参数；新旧Q都读原K，pre-RoPE FP32 RMS→每key bin八probe log-mean-exp→31bin softmax。
- `core.analyze_frozen_step`：拒绝裁head/probe、改probe顺序或改step。所有query probe身份与head等权拼接sqrt概率；float64逐差平方和，不用Gram。η=64eps仅为浮点并列判定。
- `core.summarize`/`summarize_pair`：保留全部候选距离矩阵/并列集合/来源与坐标margin，固定62相关query（20交换+42未交换）；缺步则pending、汇总null，不填0。数组由调用者保留远端，报告只应回小JSON；本包不写实际结果。

判读为非对称：新Q更接近原内容来源可支持此参考latent通路的内容响应；若仍识别当前位置，可能来自位置、坐标noise、未变Qwen3VL视觉context或原目标状态等，不做单因果归因。前一124/124结果同时改变空间身份保留与head联合聚合，亦不能单因果归为空间池化。对换不是自然平滑时移。

真实执行仍缺：精确恢复并固定同一条件noise，保存noise/augmented_rows SHA；相同软件/后端下的单forward adapter；每步原条件完整rawAV x0和raw/actual QK逐元素零扰动核验；独立审查和root GPU发布。旧历史REPLAY_GATE=false保持。当前controller_released=false；禁止把CPU READY当运行READY。

条件noise只能按patchified `[30176,96]` 在CPU以float32采样；每条件/每forward重新用相同seed2026101701，不加step。真实prepared payload的list/dict/refs与cond_video_latents别名关系尚未接通；未来须让两个引用指向同一新Z副本，原payload/list/dict/layout/tensor不改。当前构造函数只处理独立NumPy数组，不冒充模型payload适配器。
