# short_0177 v2 队列误停诊断与最小修复

v2 native 在 15 次完整 forward、750 个 block 后仍按约 23.6 秒/步前进。队列在 18:03:27 判定 `waiting_stalled`，末次完整 forward 的审计更新距此 20.28 秒。直接原因是 manifest 没有顶层 `progress_file`；原队列只观察固定的 running 状态、结束后才出现的 history，以及可选进度文件 mtime。metadata 中的 router/timing 路径仅供结果处理使用。

队列从首次 running 到 stalled 为 900.0565 秒；退出码 2 触发 worker 的 finally 清理，停止自有服务。`evidence_v2/` 原样保存状态、事件、日志、两份审计、manifest、队列与 worker 源码，并附 SHA 清单。

修复保持原队列、科学图、种子和区间算法：

1. 新 v3 每个 manifest 添加顶层 `progress_file`，精确指向本 lane、本 job 唯一 `__a1` 的 router JSON。
2. worker 的 `--stall-timeout` 从 900 改成 1800。它是统一无新进展阈值；每次 router 更新重新计时。现有 7200 秒 arm 总时限、一次 attempt、零 service restart 保留。
3. 将本目录 `progress_binding.py` 放入新 package 的 scripts，在 admission.preflight 中调用 `validate_progress_bindings(root)`，位置在服务启动之前。该函数核对唯一 a1、cohort、manifest、实际 graph 写入路径及 fresh 无 symlink 的审计位置。

实际 router 写盘发生在两次初始化、每次完整 50-block forward 完成、异常记录三个阶段；没有周期性空闲刷新。原队列已有的 mtime 机制因此足以表达本实验进展。

验证命令：

```sh
python3 /workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/supervision/interval_short0177_20261024/runtime/v3/queue_fix/test_poll_progress.py
```

15 项 CPU 回归直接调用未修改的 `Runner.poll`，覆盖旧误停复现、持续采样超越原阈值、1200 秒冷加载、真实无进展超时、API 错误，以及六配置绑定与旧路径/旧文件/a2/symlink/graph 不一致拒绝。远端没有写入或启动操作。
