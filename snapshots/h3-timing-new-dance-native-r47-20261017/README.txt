R47 two new fixed-source Native screens, prepared2026-10-17

1.10264579 window studio -> Sam Altman;2.6980766 gym -> Elon Musk. Each seed2026101701,141frames24fps1312x736,Euler20 CFG1,sigma12/3,noLoRA,nativeSDPA.
Only root may deploy/admit GPU2 UUID GPU-REDACTED port8509 after R46 release. admission starts false.
Preflight: python scripts/preflight.py. LocalCPU test runner: python tests/run_local_cpu.py <attempt>. Manifest: python scripts/build_manifest.py <root>. Actual-Comfy CPU smoke prepared tests/real_comfy_cached_queue_smoke.py --core <existing core>; root-authorized temporary CPU stage attempt2 passed; formal production deployment remains pending root.
Formal launch after root review: launch_remote.py --service-only creates registered futureCUDA PID; root registers exactpeer, atomically copies exactready togo, waitsHTTP, starts controller with exactPID/startticks. Controller serializes fixedtwo jobs, holds at completion for archive or1800sec, then exact-owned cleanup.
Inputs and probes in inputs/design. Before outcomes fixedsource selection/prompt/seed available. Native outputs used to inspect whether timing errors occur; no motion diagnosis from titles. Whole-window five fixed intervals and186 correlated scan descriptors may be evaluated later, retainingUNKNOWN.
Parent numerical/runtime hashes in configs/runtime_kernel_hashes.json, parent provenance/model hashes frozen. Inherited historical full model SHA reused with live size/mtime/core checks; actualbackend dispatch and costs require generation logs.
