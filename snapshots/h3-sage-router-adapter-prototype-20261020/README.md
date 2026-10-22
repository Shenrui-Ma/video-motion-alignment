# H3 router Sage 接口兼容原型

本目录是独立工程原型，未接入 R141b/R142 生产节点，未启动 GPU、下载文件或安装依赖。真实 Sage CUDA、H3 速度、视频质量均待验证；此工作属于已有后端与已有路由公式的工程接入。

## 接口与数值约定

`SageAttentionLSE()(q, k, v)` 接受路由器现有的 `[B,H,N,D]` 输入，返回相同布局的 O 和 `[B,H,Q]`、FP32、自然对数 LSE。Q 长度可不同于 K/V；首版只支持相同头数、相同 head dimension 的 fp16/bf16 QKV，D≤128，无 causal、mask、dropout 或 GQA 扩展。

适配器调用缓存源码中的公开 `sageattn_qk_int8_pv_fp16_cuda`，固定：

- `tensor_layout="NHD"`，通过转置加 contiguous 转换输入输出。
- `return_lse=True`、`smooth_k=True`、`smooth_v=False`。
- `qk_quant_gran="per_warp"`、`pv_accum_dtype="fp32"`，缩放按原始 D 的 `D**-0.5`。

该公开 API 在返回处已经完成 log2→ln 和 `smooth_k` 均值修正。适配器直接保留 LSE，不再次换底或加均值。缓存实现的 `q.size(2)` / `k.size(2)` 按头数读取，HND 下会读到序列长度，因此明确使用 NHD。这里的 FP32 是 PV **累加**精度；该 vendor 路径仍把 V 转成 FP16。

默认后端只接受 CUDA，没有静默回退。CPU 检查通过显式注入符合相同公开 API 契约的后端进行；注入后端的数值正确性由调用方负责。适配器检查形状、dtype 和 device，有限值与数值误差由验证脚本集中检查，避免在每次注意力调用时增加 GPU 同步。

当前 router 已有 `attention=` 注入接口。未来在隔离验证程序中的调用形式为：

```python
from adapter import SageAttentionLSE

out = route_attention(
    q, k, v, heads, plan,
    mode="mass_preserve", alpha=1.0,
    attention=SageAttentionLSE(),
)
```

这段示例没有注册节点或替换 `forward`。历史 H3 Sage 节点会替换整个 `forward` 且不返回 LSE，不应作为此原型的接入口。

## 文件与 CPU 证据

| 文件 | 用途 |
|---|---|
| `adapter.py` | 最小 `(q,k,v)→(O,ln LSE)` 适配器 |
| `diagnostics.py` | 小 QKV 的 FP32 oracle、显式 Flash 接口、未经 clamp 的 FP32 路由公式 |
| `validate_gpu.py` | 未来 GPU 比较、源码哈希检查、原始误差记录 |
| `tests/test_adapter.py` | 12 项布局、单位、dtype、公式、失败行为、输入原位修改检查 |
| `tests/test_router_seam.py` | 可选只读导入现有 router，核对实际注入接口 |
| `provenance.json` | 缓存与生产只读源码路径、哈希、对应行号 |
| `target_source_audit.json` | .41 目标现有 Sage 的函数级源码差异和明确审阅后的哈希 |
| `cpu_validation.json` | 本次 CPU 检查结果和实际运行命令 |

本机复用已有环境 `diffsynth-h3-next-study-20261013/.venv`，PyTorch 2.10.0。13 项 CPU 测试通过，Ruff 检查通过。测试覆盖不同 Q/K 长度、参考子段、NHD 转换、fp16/bf16、错误形状与 dtype、内核异常向上传递、K 均值平移的自然 LSE 契约、参考组质量接近 0/1、α=0 精确返回、正的原始 LSE 差值不被截断，以及通过子段视图原位改 K 时能检测到原始 K 变化并失败。

现有 R142 的 α=0/0.5/1 注入结果与同一个 oracle 直接接入逐位一致；α=0 只调用全注意力一次。D=32/80 的测试验证的是适配器接口，真实 Sage 的 padding 和 CUDA 行为仍由 GPU 检查决定。

```sh
cd /Users/researcher/DevProjects/h3-sage-router-adapter-prototype-20261020
PYTHONDONTWRITEBYTECODE=1 \
H3_ROUTER_EXTENSION_PATH=/Users/researcher/DevProjects/h3-timing-oxygen-centered-control-r142-20261020/extensions/H3TemporalRouter \
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python \
  -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 \
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python \
  -m ruff check . --no-cache
```

移到其他目录时，不设置 `H3_ROUTER_EXTENSION_PATH` 即只跑独立单元测试；该只读 seam 测试会显示 skipped。

## 目标 GPU 的下一步

先在原有隔离运行时检查 GPU UUID、空闲状态、模块路径和已安装兼容性，遵守当前 GPU 任务并发限制。保留 R141b/R142 冻结；把本目录复制到独立任务目录，复用已安装 Sage 与 PyTorch，不升级共享运行时。

以下命令是待执行模板，三个 `TASK_` 值须使用目标机已核验的现有路径和空闲 GPU UUID：

```sh
TASK_GPU_UUID='GPU-填入已核验的空闲UUID'
TASK_PY='/目标机/现有兼容运行时/bin/python'
TASK_PROTOTYPE='/目标机/独立任务目录/h3-sage-router-adapter-prototype-20261020'

CUDA_VISIBLE_DEVICES="$TASK_GPU_UUID" PYTHONDONTWRITEBYTECODE=1 \
"$TASK_PY" "$TASK_PROTOTYPE/validate_gpu.py" \
  --run-gpu --device cuda:0 --dtype both \
  --output "$TASK_PROTOTYPE/results/gpu-validation-001.json"
```

已有 Sage vendor 应由该隔离运行时的既有导入配置解析；脚本会记录实际 `sageattention.core` 路径及 SHA256。默认要求与缓存源码 `eb5ca9e8047583cc3a139f788f4bf48857aa1134d47a36ad5021b153690beaf4` 一致。源码不同时先审阅新 API，再显式传 `--expected-core-sha256`；脚本不会自行修补 vendor。

已另行只读核对 .41 的现有源码，目标哈希为 `e475182fc55d6a683499e1eb4d8886fc06e050ed938d8563b090773eede2a99e`。选用的 FP16 CUDA 函数参数与 LSE/PV 路径保持一致；该目标把 `size(2)` 修为 `size(nh_dim)`，已修复缓存的 HND 头轴问题。通用 `sageattn` 另增 sm121 分派，原型直接指定 FP16 CUDA 函数，不经过它。此次检查仅使用远端 Python 标准库读源码，没有导入 Sage/PyTorch 或执行 CUDA。函数级 diff 存于 `target_source_audit.json`。

对已审阅的 .41 目标，复制原型后可使用以下明确哈希命令；仍须先填入已核验的空闲 GPU UUID 与隔离原型目录：

```sh
TASK_GPU_UUID='GPU-填入已核验的空闲UUID'
TASK_PROTOTYPE='/目标机/独立任务目录/h3-sage-router-adapter-prototype-20261020'

CUDA_VISIBLE_DEVICES="$TASK_GPU_UUID" PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps \
/data3/researcher/ComfyUI/.venv/bin/python \
  "$TASK_PROTOTYPE/validate_gpu.py" \
  --run-gpu --device cuda:0 --dtype both \
  --expected-core-sha256 e475182fc55d6a683499e1eb4d8886fc06e050ed938d8563b090773eede2a99e \
  --output "$TASK_PROTOTYPE/results/gpu-validation-001.json"
```

脚本在同一组低精度 QKV 上比较 FP32 oracle、显式 ATen Flash、Sage smooth_k 开/关：B=2、H=3、Q=19、K=131、ref=67、aligned=17，D=64/128，fp16/bf16。场景包括随机值、参考与其他组 K 均值不同、参考质量接近 0/1。

每个后端保存所有查询的原始 `L_ref-L_full`、未经 clamp 的 `exp(L_ref-L_full)`、O/LSE/参考质量/FP32 修正后 O 的误差、α=0 原样返回与有限值检查。每次 full/ref/aligned 调用前后逐元素检查完整原始 Q/K/V，记录三个布尔值；任何输入原位变化立即失败，避免污染后续对照。默认暂定上限为 O 绝对误差 0.05、LSE 0.10、质量误差 0.02、正 LSE 差值 0.001；阈值写入报告，作为微测试筛查值，后续 H3 验收需另定。失败仍保留证据并返回非零状态，异常数值显式写为字符串，不用 clamp 掩盖。

生产现有的微小正差值 clamp 保持冻结；本目录诊断公式完全不 clamp。首次通过后，再决定隔离 H3 短程数值、性能与原始输出质量验证。
