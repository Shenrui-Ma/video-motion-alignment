# GPU resource recovery appendendum

The fixed 12-job queue resumed after A_s2 succeeded on GPU UUID `GPU-REDACTED` (physical index 0). A different UID acquired that GPU; the original controller rejected the next B_s2 submission and stopped its own service. The original service, controller and watchdog were all absent before replacing any active registration. No foreign process was signalled.

Only the GPU constant in task-local `scripts/service.py` changed to `GPU-REDACTED` (actual physical index 2; earlier informal “GPU1” label was inaccurate). Both are NVIDIA A100 80GB PCIe. The selected card had no compute processes, 8 MiB used and 0% utilization before startup; the service performed its admission check again.

New service: **56283**, watchdog: **56287**, controller: **62539**, port **8445**. The unchanged controller used archived successful histories for the first three entries and submitted only the next planned `06_anime_eye_insert_b_s2`, prompt ID `24f061fe-f4df-4bd5-9dc9-e57b81f069de`. First-three job/history bytes and all existing config hashes remained unchanged.

Startup evidence confirms native PyTorch SDPA, Triton enabled, Kitchen CUDA backend disabled, and the same task-local INT8 row guard. Bootstrap, row guard, audit node and Core SHA checks match the previous runtime. Model inode/size/mtime agree; large weight payload hashes were reused, not freshly computed.

**Scientific limitation:** the A_s2/B_s2 pair now spans two physical cards. Actual prepared image/video, clean latent and AV noise equality must be verified from B_s2 audit files when they appear; this is pending at recovery handoff and must not be assumed. No new benchmark, source, graph, sample or prompt was added.

See `handoff_summary.json` and raw before/after evidence in this directory. Original `configs/runtime_actual_provenance.json` is preserved; this appendendum records the later resource-driven change.
