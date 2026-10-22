# R144 饮酒 cached conditioning 单次容量试验

可以按已批准的监测试验入口执行主任务：入口要求 adjusted high/max 至少 34/46 GiB、host MemAvailable 至少 64 GiB、raw max 剩余严格大于 8 GiB。当前约 35/47 GiB 入口到中止线约有 27 GiB 增量空间；这是试验额度，尚无 matched cached 路径的匿名峰值记录。主任务健康则继续原 20 步，失败保存诊断，不额外校准或重跑。

只复制 `capacity_trial.py` 到独立 cached variant 的 `scripts/`。冻结 SHA256：

`b4a84c938173f7790e0e9ad69ae6580d19d9c7069c5ed7528302e582cbb3d18b`

服务登记后、CUDA GO 前，由根控制器启动并保持监督：

```sh
CASE_ROOT=/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/short_0358_cached_conditions
# ATTEMPT_DIR 由原 root_run_online 控制器绑定，必须为新 attempt。
/data3/researcher/ComfyUI/.venv/bin/python \
  "$CASE_ROOT/scripts/capacity_trial.py" --root "$CASE_ROOT" \
  --output "$ATTEMPT_DIR/CAPACITY_TRIAL.jsonl" \
  --ready "$ATTEMPT_DIR/CAPACITY_MONITOR_READY.json"
```

READY 包含 `passed, owner, monitor_identity, policy, entry`。根控制器核对 owner 的 PID、UID、start_ticks 和原始 NUL argv SHA256，并确认监测进程活着，才发布 CUDA GO。原 lease watchdog 按 250 ms 监督 monitor 的确切代际；monitor 意外消失则停止本次 service。根控制器负责最终 service/observer 清理、CUDA 释放与失败记录，monitor 非零退出不得发布成功 gate。

监测每 250 ms 读取服务的全部有限 cgroup 祖先、anon/current、扣除受限可回收文件页后的占用、events、PSI，以及已登记本任务进程的 RssAnon/VmRSS/VmHWM。维持 6 GiB 文件缓存保留量。任一条件达到即通过 pidfd 向本次服务及登记父链内的确切进程发送 SIGTERM：

- adjusted high ≤ 8 GiB 或 max ≤ 20 GiB。
- raw max 剩余 ≤ 8 GiB，或 host MemAvailable ≤ 40 GiB。
- 相对入口的 max/oom/oom_kill 计数增加或重置。
- some 或 full PSI avg10 > 1.0 连续两次；入口已超过则不准入。
- 读取/格式异常（仅原 observer 的非原子登记 JSON 半写允许总计 50 ms 有界重读，持续损坏仍中止）。日志、目录、READY 写入或其他外层异常也会停止已绑定服务。

memory.high 计数单独增加记入日志。未登记进程、其他 UID、复用 PID 或保护 PID 1646285 均不发信号；不用 killpg、名称匹配或进程枚举。原服务正常结束返回 0。无法捕获的 SIGKILL/宿主故障由根控制器的独立 watchdog 处理。原 main 40 GiB / decoder 16 GiB GPU 门保持不变。

## 预算依据

目标 safetensors 元数据的 tensor storage：DiT 19.5301 GiB，video VAE 4.8501 GiB，audio VAE 0.5636 GiB；四缓存 tensor 合计 0.1101 GiB，零 target 约 12 MB，107 帧 FP32 RGB 约 1.1547 GiB。以上是存储/数组体积，不能直接相加作为 RSS 上界。

源码确认 DiT 大部分 INT8 使用 mmap 后的同 dtype/device storage，未发现全模型统一 FP32 展开；model patcher 克隆共享模型。VAE 装载、dtype 转换、独立 observer 的 VAE/CPU RGB、最终 decode 触发模型 CPU offload、分配器保留与短时副本仍可能显著增加匿名内存。cached loader 跳过 Qwen 和参考 RGB 编码；单独 CPU 等价证明的 RGB mmap 不在实际 loader 路径。没有可信的 cached RssAnon/VmHWM 历史峰值，因此采用带中止线的主任务试验。

## 验证

19 个 stdlib CPU 测试与 Ruff 通过。测试覆盖入口/中止边界、PSI/events、PID 复用（含 pidfd 打开期间复用）、其他 UID/保护 PID、未登记进程、写入故障退出、正常退出及真实 R133 父链。实际 R133 服务 1937158 → observer 1940173 → decoder 1940277 / pose 1940884 的 UID/start_ticks/cmd hash 全部吻合。

目标 Python 已只读确认 `pidfd_open` 和 `pidfd_send_signal` 可用，并成功打开/关闭自身 pidfd；未发送信号。此目录准备过程中未启动 GPU、安装依赖、修改远端或改动原失败证据。

证据：`TARGET_HEADERS_AND_LOAD_CODE.json`、`LOAD_ALLOCATION_CODE.json`、`OFFLOAD_AND_VAE_CODE.json`、`RAM_CACHE_CODE.json`、`R133_ACTUAL_PARENT_CHAIN.json`、`R133_ACTUAL_SERVICE.json`、`TARGET_PIDFD_CAPABILITY.json`。`VALIDATION.json` 保存最终测试输出，`FREEZE.json` 保存文件 SHA256。
