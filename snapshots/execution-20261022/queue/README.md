# ComfyUI 持久化顺序推理队列

仅使用 Python 标准库；视频校验使用已安装的 `ffprobe`。脚本在 ComfyUI 所在机器运行，通过本机 HTTP API 提交任务，直接读取其 output 目录。每次提交一条，确认其完成或明确失败后处理下一条。

## CLI

```sh
python3 durable_comfy_queue.py \
  --manifest /path/jobs.json \
  --state-dir /path/queue_state \
  --comfy-url http://127.0.0.1:8188 \
  --output-root /path/ComfyUI/output \
  --max-attempts 2 \
  --stall-timeout 14400 \
  --restart-command '["/path/python","/path/restart_owned_comfy.py"]'
```

- `--restart-command` 可省略。提供时，命令必须确认旧的**自有**服务已停止，启动新服务，并等到其 API 健康后返回 0。脚本按 argv 执行，经过 shell 的语法需要显式提供 shell 命令。
- 提交前先检查 API 健康，服务不可用时等待或重启，不消耗任务尝试次数。
- 原 prompt 在空 queue/history 中连续消失 120 秒时，确认受管重启后记录为中断，再按尝试上限重试；`--missing-prompt-grace` 可调整等待时间。
- 持续断联默认 120 秒后尝试重启；持久化计数限制同一个 state-dir 最多 2 次服务重启，可用 `--max-service-restarts` 调整。
- 成功重启后，原 prompt_id 仍存在于 queue/history 则继续跟踪；已经消失则记录被中断的尝试，按单条重试上限重新提交。
- `--stall-timeout` 默认 4 小时。history 内容、队列阶段变化或 `progress_file` 文件更新时间都算进度。停滞或持续失联达到上限会退出 2 并保留 prompt_id；再运行同命令继续跟踪。
- 批次结束直接退出。服务模型卸载、退出进程和 GPU 释放由外层 supervisor 在 runner 退出后执行。

## Manifest

```json
{
  "jobs": [
    {
      "id": "ive_short_0252_weak_all",
      "graph": "graphs/ive_short_0252_weak_all.json",
      "expected_output_prefix": "r151/ive_short_0252_weak_all",
      "progress_file": "/path/logs/comfy.log",
      "metadata": {
        "dataset": "IVEBench",
        "timing_file": "/path/audit/timing/{attempt_id}.json"
      }
    }
  ]
}
```

`graph` 可为裸 ComfyUI API 节点图，或 `{"prompt": 节点图}`。相对路径按 manifest 所在目录解析。`expected_output_prefix` 匹配 history 中的 `subfolder/filename`；支持 mp4/webm/mov/mkv/avi。

追加实际实验任务时，原子替换 manifest 即可。runner 每做完一条重新读取文件，自动接上新增任务；全部处理完退出，不空转。相同 job ID 的 graph 内容必须保持一致；参数变化使用新 job ID。

每次尝试 ID 为 `<job_id>__a<N>`。提交前递归处理图和 job 配置：

- 所有名为 `run_id` 的字段替换为此次尝试 ID；
- 所有字符串中的 `{attempt_id}` 与 `{run_id}` 替换为此次尝试 ID；
- 其他数值和字符串保持原值。

这保证重试时审计节点得到新的 run_id，原有记录可保留。提交前写入 state.json 的 intent 和 attempt_token；提交响应丢失或进程中断后，使用 ComfyUI extra_data 中的 durable_job_id、durable_attempt_token 找回同一 prompt。查不到时保留 `submission_unknown`，跳过该条并处理后续任务；再次启动时重新查找，不自动重复提交未知请求。

## 采样计时

推荐节点直接写 `metadata.timing_file` 所指的 JSON：

```json
{"sampler_wall_seconds": 1200.0, "per_step_seconds": [60.1, 59.9]}
```

runner 保存采样总时长、逐步时长和逐步平均值。`sampler_wall_seconds` 由 sampler 实测，不从总执行时间推算。

也支持 job 顶层 `sampling_events_path` 指定 JSONL，每条必须带当前 `prompt_id`：

```json
{"prompt_id":"...","event":"sampling_start","timestamp":123.0}
{"prompt_id":"...","event":"sampling_step","duration_seconds":60.0}
{"prompt_id":"...","event":"sampling_end","timestamp":183.0}
```

事件时间单位为秒。ComfyUI history 的 execution_start/execution_success 时间戳为毫秒，另记 `execution_seconds`。缺失采样审计时，sampling 字段为 null，不用 execution_seconds/steps 代替。

## 持久化产物与退出码

- `state.json`：状态、尝试次数、prompt_id、失败原因与重试历史。
- `history/<prompt_id>.json`：原始 ComfyUI history。
- `results/<job_id>.json`：已校验视频路径、ffprobe 信息、SHA256、计时与 metadata。
- `events.jsonl`：提交、进度、失败、恢复、完成的事件。
- `runner.lock`：操作系统 flock 锁，进程死亡后自动释放。

退出码：0 全部完成；1 有明确失败、无效任务或提交状态未知，其他任务已处理；2 停滞、长时间断联、重复 runner 或配置错误。

失败任务默认最多尝试两次，再继续下一条。队列不会触碰其他用户的 ComfyUI 服务、请求或 GPU 进程。共享 state-dir 防止双 runner；同一机器若有多个 runner，各自使用独立 ComfyUI 端口和 state-dir。

## CPU 验证

```sh
python3 -m unittest -v test_durable_comfy_queue.py
python3 -m py_compile durable_comfy_queue.py test_durable_comfy_queue.py
```

Mock HTTP server 验证：失败重试并继续、重启恢复、提交已接受但响应丢失、未知提交不重复、重复 runner 锁、停滞保留 prompt、采样计时来源、运行中追加任务、attempt run_id、受管服务重启、无效图后继续、任务间服务崩溃恢复、快速重启丢失 history 的恢复。测试使用模拟 ffprobe 输出；实际推理完成时使用真正 ffprobe 验证文件。
