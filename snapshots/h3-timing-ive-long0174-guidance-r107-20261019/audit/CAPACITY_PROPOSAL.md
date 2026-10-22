# R107 单进程容量准入提案

状态：root 已审阅并授权接入管理层；生产模块为 `scripts/working_set_capacity.py`，配套边界测试纳入完整 98 项 CPU 检查。R107 执行期间 `.41` 只运行这一项 H3，不并行本用户的 R103 或 MF。

## 证据

R96 的 585 次真实采样中，首个任务所在独立 session 的总收费内存峰值为 67,952,947,200 B（63.286 GiB），整批最高为 77,757,599,744 B（72.417 GiB）。后者出现在第二/第三个任务附近。历史未记录 `memory.stat`，匿名内存峰值未知。整批父 cgroup `high` 新增 5127，`max/oom/oom_kill` 均新增 0。不能将这些结果理解为匿名内存需求或保证未来峰值。

R99 在 `.9`，只保存了显存采样，没有可用的 CPU/cgroup 峰值记录。它不作为本准入容量依据。

## 公式

对每个具有有限 `memory.high` 或 `memory.max` 的祖先分别计算，单位均为字节：

```
disk_cache = min(max(0, file - shmem), active_file + inactive_file)
clean_unmapped = max(0, disk_cache - file_mapped - file_dirty - file_writeback)
credit = min(memory.current, max(0, clean_unmapped - 8 GiB))
adjusted_current = memory.current - credit
high_headroom = memory.high - adjusted_current
max_headroom = memory.max - adjusted_current
```

`min` 避免计数器存在瞬时差异时扩大缓存额度。共享内存、映射文件、未写回页、正在写回的页均排除；再保留 8 GiB 文件缓存。相互重叠的排除项会低估可回收量。读取 stat 前后取较大的 `memory.current`。这些读取不是原子快照，仍需启动前和 GO 前重新检测。

条件全部满足才准入：每个有限 `high` 余量至少 64 GiB；每个有限 `max` 余量至少 76 GiB；主机 `MemAvailable` 至少 64 GiB（root 审阅后提高）；有限祖先 PSI `some/full avg10` 均不超过 1%；UID、父 cgroup 100/112 GiB 限额匹配。任何缺失、异常字段均拒绝。

64 GiB 保留原冷载预算并超过历史首任务 63.286 GiB 的总峰值。76 GiB 硬限额预算超过整批总峰值 72.417 GiB 约 3.58 GiB，已另外在工作集估计中保留 8 GiB 缓存。这是基于总收费内存历史的保守运行边界，并非匿名峰值估计。

## 当前实测与边界

具体字节和 PSI/events 保存在 `WORKING_SET_PROPOSAL_CURRENT.json`。本次 high/max 余量为 68,791,672,832 / 81,676,574,720 B，约 64.067 / 76.067 GiB，刚达到条件；后续任何小幅匿名内存增长均可能使它重新排队。主机 MemAvailable 229,917,020,160 B。不得靠放宽门限追逐准入。

本地和目标机器各 16 项容量边界测试通过，完整生产测试各 98 项通过：精确边界、差一字节、硬限额独立阻断、更紧后代限额、缓存排除、低缓存、缺失/负值/NaN/非法单位、UID/限额变化、PSI、主机余量、输入不可变性。原始历史 high 累积值不作为本次失败，启动后记录增量。

不会执行 drop_caches、memory.reclaim、修改限额或触碰其他用户进程。Linux 正常内存回收仍可能导致延迟；记录 `current/stat/events/PSI` 轨迹。运行期保留现有故障处理，不因单次可选遥测失败而取消健康推理。

## 文件

- `working_set_proposal.py`：独立提案计算与 fresh 只读采样。
- `test_working_set_proposal.py`：16 项测试。
- `WORKING_SET_PROPOSAL_TESTS.log`、`WORKING_SET_PROPOSAL_TARGET_TESTS.log`：两端通过记录。
- `WORKING_SET_PROPOSAL_CURRENT.json`：当前精确实测。
- `CAPACITY_REVIEW_BEFORE_LAUNCH.json`：R96 历史和当前原始字段。

## 最终部署修订

root 后续授权将额外保留缓存从8GiB改为6GiB，其他 high64/max76/host64、PSI 与文件排除项保持。理由：缓存预算属于额外管理余量，历史匿名峰值未知；6GiB仍保留缓存，并增加约2GiB启动波动余量。生产公式中 credit 使用6GiB；上文8GiB为最初提案。生产最终72文件seal b12267486bf6abdb635a6bfa8f5356dcec07326ab1a4c16dacb5bbd78593a351，本地与目标99测试通过。attempt1保护性停止在服务之前，attempt2已注册。
