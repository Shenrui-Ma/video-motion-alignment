# 单前向内容/坐标诊断实现审查

独立审查覆盖真实 H3 包装域、条件噪声来源、输入身份和有限调用终态；没有读取真实 tensor、权重，没有 GPU 调用。

## 通过的实现结构

生产入口硬限定 `two_zero_only`，拒绝自动交换scope；内部四调用只保留合成控制流测试。新输出节点真正调用 `guider.sample → KSAMPLER → ContentCoordinateSampler`。条件由原 `process_conds` 预处理一次；有限 sampler 从同一未使用 native router 模板为每个保存的 step 建立独立状态。顺序为 zero9、zero19，通过后才可 swap9、swap19；每次直接读取保存的实际 packed x，从不由前一次输出演化下一次。callback 不执行，不构造20步轨迹或视频。完整21σ与 AV shift12/3、multiplier1000、noise_scale1 保留。

条件复制只替换 reference Z 的容器/张量，refs 与 cond_video_latents 指向同一新 Z；Z 的 dtype/device 保持。原方法生成噪声及混合 rows，实例级 observer 在相同 Torch 算术上独立重建并逐元素比较，返回原方法的原对象。全局 RNG 不改。准备后的 Qwen 多模态 context、参考元数据、位置、目标 AV 均校验不变，finally 恢复条件/临时方法/hook。

每次实际调用要求1 forward、50 blocks、完整六操作 backend snapshot，200 次成功 Triton dispatch，其他后端和错误为0。zero 对整个 raw AV x0、raw/actual Q_C/Q_R/K_R、norm 权重与eps、位置/RoPE/完整probe metadata要求逐元素相同。swap仍核位置/norm等metadata，但QK内容允许变化。所有 56 heads×8 probes 与31有效时间bin保留。

## 审查发现并已修复

1. 真实 live capture 使用 `forward_identity.state_file_sha256`，原初版误取 `state_sha256`。已改为实际字段，并将case/method/trajectory/step、完整sigma与state tensor signature一同核对。
2. 真实 dispatch auditor 使用 `attempted_calls/successful_calls/failed_calls`。已纠正字段，并拒绝缺失任一六backend-operation项、缺counter、非整数/负数、counter倒退或任何非Triton执行。
3. sampler内成功不再直接写最终passed。先记 `forwards_complete / passed=false`，外层实际视频和audio/4归一化精确通过后才最终complete；异常保留failed证据。
4. native router全部科学参数与原contract一致，避免仅mode相同却图参数漂移；完整AV与QK形状/有限性及固定probe支持在真实tensor解码后核查。

## 独立验证

先对 `655ff1d0ad0c` 包运行7项；最终在 .81 隔离 CPU 目录对生产zero-only冻结 `b5d556c3cd0a` 包运行8项测试，0.429秒全部通过。逐项 SHA 核对14个源码/小metadata文件。测试使用合成完整packed AV及共享BF16 QK零张量，不解码任何真实实验tensor。覆盖实际live metadata样式、哈希先于decode、六backend字段/类型失败、全部QK/元数据扰动、payload异常恢复、外层音频错误不能留下passed，并新增production combined-scope在读取tensor前拒绝。

作者的集成测试直接执行 ContentCoordinateSampler.__call__ 与实际 KSAMPLER 源码，但 DiT/capture使用廉价合成fixture，验证四条调用顺序与fresh router、zero19失败止于两条、模型异常清理。此处所用mock范围已在测试中明确；它核验控制流，不是实际H3数值复放证据。

## 下一门槛

CPU代码通过后，资源层仍需绑定最终READY和派生图/源资产/同环境运行参数，重新核原state、noise/cache/model、native图身份以及资源预算；本轮只供root资源安排后另行释放2zero；真实两zero先回传核验，再独立决定内容交换，当前生产入口不放行swap。真实zero结果必须保持exact，任何一步失败即停止，旧历史failed gate保持原样。未达到这一步前，内容读取、动作相位和alpha控制均无新真实结论。

目前所需原state与cache确有小metadata记录，不需要为接口验证重跑整片。仅在实际zero失败且能定位为不可恢复prepared值时，才讨论新的被动记录；不能自动放宽gate或重跑整片。
