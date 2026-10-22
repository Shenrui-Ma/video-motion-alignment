# Retry only the verified, pre-sampling error

Root reports attempt1: coordinator31119 exited1; service31126 absent and absent
from GPU; supervisor31124/watchdog31130 exited0; controller32187 exited1;
primary admission restored, `cleanup_errors=[]`, and nvidia-smi shows only primary
49019. Root has preserved the attempt's logs/processes locally under
`audit/transfer_attempt1`. These are supplied completion facts, not remote checks
performed by this staging agent.

V1 failed at `H3EventAudit.audit_root`, before sampling, because a full path
component was still pinned to the primary instance. The repair is exactly:

- Change that guard to require a resolved descendant of the complete transfer
  root, rejecting the primary directory, unrelated roots, prefix siblings,
  `..` escape, and symlink escape.
- Change the two EventAudit input defaults to the transfer audit directory.
- No change to encoding, tokenization, noise generation, attention, schedule,
  graph, seed, run ID, input media, or other extension code.

The v1 package is archived in `archive/v1_frozen_before_audit_root_fix.tar.gz` with
its own hash manifest. New tests call the actual four graph paths and noise entry
point on CPU. They also compare ASTs after removing only the path guard/defaults.

## Minimal remote retirement before root relaunch

Do not run `prepare_runtime.py`; do not wipe the instance. Verify again that the
listed processes are gone and no service/helper holds the old locks. In a fresh
attempt archive **inside this transfer instance**, move:

1. The entire `logs/` directory (includes job JSON/history, controller status,
   backend logs, resource logs and service stdout).
2. The entire `processes/` directory (includes old locks, gate/releases, exact PID
   records, cleanup, admission snapshots and coordinator journal).
3. `configs/runtime_provenance.json`, if present; otherwise prepare() would
   overwrite the v1 code fingerprint during retry.
4. A copy of the current `configs/admission.json` and the prior expected-primary
   identity file used by root (`configs/expected_primary.json`, or its actual name).
5. The old `audit/bundle_manifest.json`, `runtime_delta.patch`, verification/test
   records, and guard inventory before replacing those deployment manifests.

Then recreate empty `logs/` and `processes/`. The coordinator creates other needed
directories itself. Keep `input/`, `inputs/`, models/core links, `custom_nodes/`,
`temp/`, `user/`, and `screen.db`; none is the durable job/provenance barrier. The
new service process has a fresh in-memory Comfy cache. SaveVideo history remains
in the archived job/history files; SQLite may retain an additional old error record.

Before retry, inspect `audit/` and `output/` for any graph-run artifacts. The first
guard failure should precede conditioning/noise/x0/router output, but this must be
checked, not assumed. If any exist, move them into the same failed-attempt archive
without modifying their bytes. In particular no existing directory
`audit/x0/s05_full_seed2_native_x0` or routing/conditioning/noise record for those
four run IDs may be silently reused. Preserve an unexpected output video too.
Do not archive or delete the shared primary task's files.

Upload only the patched `extensions/H3EventAudit/__init__.py`, new tests/fixture,
updated README/retry document and new audit manifest/test/diff/inventory files.
No service/coordinator or science graph changes are required for this repair.
Do not overwrite the live admission file with the disabled staging template.

Use the same four graph/run IDs only after the clearly failed attempt records are
retired as above. This is an explicit error retry with a new coordinator launch ID,
new PID and fresh gate; it is not an automatic replay of an uncertain submission.
The original source seed/noise protocol and comparisons remain unchanged.

Finally re-run the real-node CPU tests remotely with the existing Comfy torch
Python and `CUDA_VISIBLE_DEVICES=''`, verify the new manifest, run fresh primary
identity/resource inspection, and explicitly run the existing coordinator. If
primary has already ended or changed identity, its initial live-primary handshake
must not be bypassed; root must separately review an alternative admission plan.
