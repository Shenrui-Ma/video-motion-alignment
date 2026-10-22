# One bounded B1 retry

`05_real_megumi_v_b_s1` was resubmitted at 2026-10-13T17:10:12.150974+08:00 as prompt `bcbee72c-1d1d-478c-8ae8-23b6950c5767` on the same GPU UUID `GPU-REDACTED` (physical index 2). Original command, cache policy, graph, models, sampler, attention, steps, flags, sealed 12-cell matrix and seed are unchanged.

New service **42286**, controller **54404**, watchdog **47672**, CPU supervisor **42233**. The supervisor creates the service using unchanged `service.start`, waits for its direct child, then records exit code/signal in `processes/service_exit_42286.json` and exits. CPU tests verified exit 0, exit 7 and signal 15. This adds exit observability; it cannot identify a signal sender or survive being killed itself.

The incomplete original job/audit/config/logs/registries are preserved in `attempts/05b1_service_disappeared/` on both hosts, including six references to existing canonical tensor/cache payloads without duplicating them. Only the incomplete B1 active job registration moved aside. Five completed cells were skipped using archived success histories, and all their job/history/video hashes remained unchanged. All frozen configs and runtime source hashes remained unchanged, apart from adding the standalone supervisor script.

At the final recovery probe, the active B1 audit files still had pre-retry modification times. Equality against those old files is **not new-run evidence**. Rewritten conditioning/noise must be compared against the archived original manifests later. No completion of B1 or the remaining queue is claimed here.

Follow-up freshness probe: fresh_manifests_exactly_equal_to_original. See `recovery_audit_freshness_probe.json`; full pair/blob validation remains with the root.
