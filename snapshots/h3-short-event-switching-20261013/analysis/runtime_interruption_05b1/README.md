# 05 B_s1 execution interruption

The service disappeared between 2026-10-13T16:53:54.087805+08:00 and 2026-10-13T16:54:24.180708+08:00 (Asia/Shanghai). The controller then failed because `job.status` found the service absent, and its `finally` recorded cleanup. Service 56283, controller 62539 and watchdog 56287 are absent.

The first five formal jobs have saved `success` job/history records. `05_real_megumi_v_b_s1` has no saved history and no output video; its graph explicitly saves with that filename prefix. The last sampler log is 16/20. It must remain incomplete.

The **exit cause is unresolved**. The log has no terminating Python/CUDA traceback. Readable kernel ring has no OOM/Xid/segfault/current-PID event after this service start. Its older OOM events and PID13549 Xid are unrelated earlier events. Journal and `/var/log/messages` access is restricted; no exit status or signal receipt was retained. The 9-hour watchdog lease, 8-hour controller deadline and 1-hour job timeout had not expired. An OOM or external signal cannot be concluded from the disappearance.

Last ten GPU samples were stable at 63,460 MiB used, 17,590 MiB free, 100% utilization and 76 C. These snapshots do not prove peak usage. At the read-only probe, all four A100s were idle, port 8445 free and about 194 GiB host memory available. Persistent `/dev/sda` errors exist, but the task and models are on `/dev/sdb`; Python is on `/dev/nvme0n1p1`. This does not establish a disk cause.

No restart, retry, parameter edit or process signal was performed. Resources currently permit a fresh admission check, but resuming requires the root to preserve this incomplete attempt and explicitly handle its stale job record before a same-graph retry. The five successes must remain untouched. Full evidence is in `diagnosis.json` and the copied snapshots.
