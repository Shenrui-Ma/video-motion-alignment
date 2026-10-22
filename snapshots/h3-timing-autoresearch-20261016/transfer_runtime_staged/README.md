# Isolated transfer runtime — v2 root-guard repair staged

This bundle contains four already reviewed transfer graphs and an independent
runtime. Root deployed v1; its first graph failed before sampling because the
copied H3EventAudit guard still required the primary directory. Root verified
cleanup and admission restoration. V2 changes that path guard and its two default
paths only; this agent has not deployed v2. Preserve the failed attempt and follow
`RETRY_AFTER_EXPLICIT_ERROR.md` before explicitly relaunching.

| Item | Pinned value |
|---|---|
| Host | existing `.9` research server |
| New root | `/data5/researcher/h3_runs/timing_autoresearch_20261016_transfer0` |
| New GPU | GPU 0 / `GPU-REDACTED` |
| New port | `127.0.0.1:8461` |
| Primary root | `/data5/researcher/h3_runs/timing_autoresearch_20261016` |
| Primary port/GPU | `8460` / `GPU-REDACTED` |
| Expected primary now | PID `49019`; UID/start ticks/raw-command SHA must be freshly inspected |
| Core, Python, dependencies, models | same read-only paths as the primary |

Do not run the old `prepare_runtime.py`. Do not copy models, install packages,
change shared Comfy files or rsync with `--delete`. For first deployment, upload
the bundle to a **new** pinned directory. For this v2 repair of the existing
instance, use only the targeted updates and failed-attempt retirement described
in `RETRY_AFTER_EXPLICIT_ERROR.md`. Root owns deployment; this agent stages files.

## Graph invariants

Queue order is source05 seed2026101312 native, same-seed mass-preserve;
source07 seed2026101311 native, same-seed mass-preserve. Geometry remains
1312×736, 141 frames, 24 fps, 20 Euler steps, original prompt/checkpoints/INT8
linear implementation, frozen explicit Flash attention and x0 recorder. Window
50–65 applies to source05; 54–69 to source07. Alpha1/radius0/offset0 and half-open
blocks `[0,50)`, steps `[0,20)` are unchanged. Each graph differs from its reviewed
source only by the audit/output-root prefix. Input bytes and numerical node code
are copied exactly. V2 differs only in H3EventAudit output-path validation/defaults;
an AST test checks the rest of that node is unchanged. Source/staged hashes and differences
are in `audit/bundle_manifest.json` and `audit/runtime_delta.patch`.

Source07 is a known historical failure and related choreography. These runs are
not a blind held-out benchmark, a complete source×seed factorial, or evidence of
overall success frequency. The runtime makes no methodological novelty claim.

## Explicit activation, only by root after review

The commands below are instructions for a later remote session, **not commands
already run**. Run from the new remote directory. First perform read-only
inspection and save its output (do not invent the identity fields):

```sh
python3 scripts/coordinate_launch.py inspect --primary-pid 49019 > configs/expected_primary.json
```

Inspect must confirm the original primary registry/identity and queue, an empty
GPU0 with at least 40,000 MiB free, at most 512 MiB used, zero utilization, and
at least 40 GiB available host RAM. It uses `nvidia-smi` only; it imports no torch.
These checks repeat at startup and immediately before releasing CUDA. If they
fail, do not lower thresholds or bypass the guard without a separate review.

Then use a durable terminal or nohup to run the coordinator in the foreground of
that session (redirect its output to this instance's logs). For example:

```sh
python3 -u scripts/coordinate_launch.py run \
  --expected-primary-file configs/expected_primary.json \
  --decision-note 'REPLACE with the reviewed hard-control result and reason to run transfer' \
  --execute
```

The sample reason must be replaced by an actual scientific go decision. There is
no automatic decision, remote launch, retry of uncertain submissions, or primary
restart. Direct `launch_remote.py` is disabled. Direct `service.py start` requires
a fresh gate signed by exact process identity and a live coordinator; without
that handshake the bootstrap never imports torch.

## Handshake and failure handling

1. Coordinator verifies the frozen payload, locks its instance and the cooperative
   primary admission writer lock, records primary queue/identity and resources.
2. Transfer admission permits only the exact primary PID + UID + start ticks +
   SHA256 of raw `/proc/PID/cmdline`. Foreign users are left alone; any unexpected
   own GPU process is refused, and GPU0 must be entirely empty.
3. Supervisor starts the real Comfy process. Before torch/PyAV/kitchen/Comfy
   imports, its bootstrap writes a ready record and waits at most 180 seconds.
   It has no CUDA context while the primary may submit another job.
4. Coordinator matches the ready PID/identity to the service registry, repeats
   resource/admission checks, and atomically appends that exact peer to primary
   admission. It saves byte-for-byte old and installed admission snapshots.
5. Watchdog starts before release. A release binds nonce, PID, UID/start/hash,
   GPU, port, root, coordinator, primary, deadline, and both admission hashes.
   Bootstrap independently verifies all fields and peers, then imports torch.
6. After required nodes are ready, the existing single-job controller executes
   the sealed queue, with original submit-once histories and per-job/batch limits.
7. The coordinator monitors its children. At completion/failure it stops only
   exact recorded transfer processes, verifies service and GPU absence, then
   restores the original primary admission only if its bytes still match the
   version installed here. Externally modified admission is preserved and flagged.

The primary must still be live during initial authorization and pre-CUDA release.
After release, its **verified natural completion** allows transfer to continue:
the primary registry must be byte-equivalent as a parsed record, controller state
must be `all_queued_jobs_complete`, cleanup must contain that exact service record
with `process_absent=true` and `own_compute_absent=true`, and its PID must actually
be absent. A bounded 45-second wait handles stop/reap/journal ordering. The normal
closing of its HTTP listener is not a failure. An abnormal exit, replaced primary
PID/registry, or unverified cleanup stops transfer. Root must not restart primary
or launch a new own GPU job (including GPU3 decoding) until transfer completes.

The watchdog detects coordinator loss and stops transfer. SIGKILL/power loss can
prevent admission restoration; the remaining entry is still bound to the old
exact identity and grants no blanket permission. Root must audit/remove it using
the saved snapshots before another run. Normal SIGINT/SIGTERM paths clean up.
No script ever signals the primary or another user's process.

## Verification and remaining limits

Run CPU tests with no GPU or model imports:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Use the existing torch CPU environment to execute the real-node path tests;
plain Python without torch skips those tests and is insufficient for v2 admission.
Tests cover all four graph paths through the actual audit guard and noise node,
traversal/symlink rejection, numerical-code identity, and a real CPU child
blocked before a sentinel, successful exact release
without torch import, timeout, stale releases/PID/identity/GPU, admission tampering,
compare-before-restore, refusing unrelated cleanup, natural primary completion,
abnormal/new-primary rejection, and graph structural identity after root rebasing.
On macOS the subprocess test injects the process-identity reader; actual Linux
`/proc`/nvidia-smi/HTTP/service lifecycle has not been exercised by this staging
task. A root-led no-GPU review/smoke and final code review remain prudent before
launch. No claim is made that this staging has run a transfer inference.

The writer lock is cooperative. Root must not edit primary admission concurrently
without respecting it; third-party noncooperating file writes cannot be made into
a filesystem compare-and-swap transaction. Shared checkpoints, core, and node
dependency files must not change during either instance. OS/driver/compiler caches
remain native; no new backend or quantization policy is introduced. Concurrent GPU
work can change wall time/host pressure, so these runs cannot support speed claims.

Important records: `processes/coordinator*.json`, `pre_cuda_*`, admission snapshots,
`service*.json`, `cleanup*.json`, `logs/controller_state.json`, each job/history,
`configs/runtime_provenance.json`, and each graph's separate audit directory.
