R27 policy replay — frozen before reading actual observations

This standalone CPU analysis writes only analysis/policy_replay/results/<name>.
Original policy/layout are byte-identical owned copies. No inference module,
Torch, VAE, pose model, remote call, service or GPU is imported or launched.

Required input: a completed single-run postrun archive with original raw JSON,
RUN_GATE, RUNTIME_GATE and FILE_INVENTORY. Raw PT data remain under the original
consumer integrity gate; only their native endpoint hash links are retained here.
Local source pose and observer JSON bytes are checked against the archived inventory.

Run after root confirms completion and local metadata is present:
python3 replay.py --archive /absolute/path/to/captured/RUN --output-name RUN
The script takes the shared local CPU lock nonblocking, uses one standard-library
thread, and exits if another consumer owns the lock. Do not hold a lock waiting.

Three policies: exact local compatible; one-step current representatives;
custom directionless measured-gain mean W2, not a MotionEcho reproduction.
UNKNOWN excluded from the mean; zero measured rows => UNKNOWN. Advanced measured
rows can contribute to the scalar but are never routed. All denominators retained.

Diagnostics: every accepted inter-step representative edge, lag delta for .3/.5,
same-feature vs shared-part-only; every component's member union and representative
RGB/bin support. Counts are overlapping hypotheses, not independent samples.
No alternate policy is integrated: no causal video quality or efficiency inference.

Synthetic coverage: initial/unknown breaks, disjoint windows/parts, strict .5,
advanced/global asymmetry, >2 lag jump retained by actual policy, overlap-chain
coverage, exact actual decision mismatch, nominal bin mapping, whole-window
inventory, path escape, completed request/response/native chains, tamper rejection.
20 tests passed attempt1; two intake binding tests added, 22 passed attempt2.
Both logs retained. No actual trajectory observations were loaded while developing.
