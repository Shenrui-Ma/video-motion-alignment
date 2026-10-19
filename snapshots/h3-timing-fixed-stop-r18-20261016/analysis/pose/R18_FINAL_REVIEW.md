# R18 fixed stop after index11: independent final review

R18's final primary motion is within the frozen±2-frame criterion: direction **+1/+1** and wrist **+1/+1** at confidence0.3/0.5. This validates the tested fixed6–11 schedule on the already selected development case. It does not validate an online stopping rule or generalization. Full6–14 still has lower primary same-frame pose error; equal lag is not equal motion/visual quality.

## Exact causal and execution binding

The only scientific change relative to R3 Full6–14 is `step_end15→12`, with `step_start6` unchanged. All indices are zero-based; the six active calls are indices6–11. Source05, Sam reference, seed2026101311,141frames,1312×736,24fps,20 Euler NFE and geometry are unchanged. Actual executed graph, conditions including pre-expansion tokenization, embedding/tags, latent/noise, complete50-file payload and router counts pass. Actual totals:20 forward calls,20 updates,20 callbacks,1000 blocks,300 routed blocks. Runtime files were not modified.

The actual11 archived tensors consist of indices5/6/7/8/9/10/11/12/15/19 plus `sampler_final`. Metadata, finite two-stream values and complete unique inventory pass. Video and audio are bitwise equal to actual R3 captures at5–10, actual R10 **chosen Full** endpoint11, and actual R10 **unchosen Native** endpoint12. This is the intended common-prefix/first-stop bridge; it is not a comparison to R10's chosen Full12. Later final evolution is measured from the new R18 run, not inferred from that bridge. All43 official completion checks pass; see `replication/r18_s05_full_6to11_official_completed_gate.json`.

## Frozen timing and common-support results

Pairs are confidence0.3 /0.5; `?` is unknown/rejected. Positive means later. Strict primary requires both direction and wrist known at both thresholds and all values within±2. No threshold or window was changed.

| Arm | 50–65 direction; wrist |69–81 direction; wrist|80–92 direction; wrist|99–111 direction; wrist|
|---|---|---|---|---|
|Native|13/13;13/12|10/?;10/?|8/?;8/?|4/4;4/4|
|R12 Native-observed feedback|3/3;4/4|2/?;2/?|2/2;2/2|1/1;1/1|
|Full6–14|1/1;1/1|0/?;0/?|1/1;1/1|1/1;1/1|
|R18 fixed6–11|1/1;1/1|0/?;0/?|1/1;1/1|1/1;1/1|

Four-arm primary same-frame errors, on identical support and shared minimum-confidence weights:

| Feature/confidence | Support | Native |Full|R12|R18|
|---|---:|---:|---:|---:|---:|
|Direction0.3|1|1.12919|0.13339|0.40463|0.18307|
|Direction0.5|0.96875|1.13937|0.13535|0.41188|0.18700|
|Wrist0.3|1|0.83309|0.15033|0.34745|0.18406|
|Wrist0.5|0.9375|0.83116|0.15219|0.34269|0.18359|

Thus R18 improves the measured residual relative to R12 but does not equal Full's shape error. Tail112–140 direction errors are Native0.09705/Full0.06681/R120.06864/R180.06786 (full support at both thresholds). Across0–140, direction errors are0.43447/0.12683/0.21226/0.13993 at0.3 (support0.98936), and0.41366/0.11728/0.20075/0.13075 at0.5 (support0.94504). All four original windows and pre/action/post/tail curves are retained in `common_support/`. Each arm-set comparison recomputes its shared confidence weights, so these values must not be numerically contrasted with another round's differently constituted arm set.

## Quality, cost and limitations

The fixed55/86/105 frames show the adult male gray-top/black-trouser edit, white curtains, cabinet, table and white bench. No gross background or silhouette collapse is visible in these samples. Hands and fast-motion areas exhibit blur/trailing; fine fingers and exact identity likeness remain unverified. Three images do not establish absence of full-clip flicker/ghosting or equal visual quality to Full. See `FINAL_VISUAL_REVIEW.json`; this is deliberately not a full quality pass.

`FINAL_SUMMARY.json` records actual whole-history walltime,20 NFE, VAE/capture timing, CPU integrity/pose/common-support time. The reduction from450 to300 correction-block calls is an executed structural count, not a proved walltime speedup. No efficiency diagnosis or extra timing experiment was conducted.

All unknown cells and original outputs are retained. The exact R18 service53576 and supervisor/watchdog/controller53508/56593/56594 were independently absent after completion; GPU2 was8MiB/0% with no compute. Other GPUs had unrelated processes, which were not touched. This is the state at the saved live snapshot, not a promise of continued availability.

This fixed schedule was selected after inspecting R10/R15 on the same case. The result establishes that stopping after11 can retain useful final alignment in this case, whereas the earlier tested R12 policy stopped too early for the strict final criterion. It does not establish a general earliest stop, prove that a particular observer measures every event correctly, or demonstrate an architectural innovation. Subsequent adaptive claims require their own actual-current-state observation and intervention controls.
