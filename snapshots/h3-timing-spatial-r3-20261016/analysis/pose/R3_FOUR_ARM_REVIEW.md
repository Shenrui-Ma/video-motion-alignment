# R3 four-arm independent evaluation

All four formal outputs were admitted from successful exact histories, copied with matching producer/local SHA256, checked against their executed configs and measured with the frozen CPU pose pipeline. No benchmark was included. All four actual conditioning and noise objects match within this round. The selected source05 failure and seed were already known; these are controlled interventions on one case, not four independent demonstrations or an estimate of population failure frequency.

## Outcome

Full, DC and SP all repair the primary window under the pre-existing absolute-lag ≤2-frame criterion at both detector thresholds. DC retains approximately the full branch's efficacy in this particular .9 setup. SP also helps substantially, but does not improve on full/DC on the frozen timing and same-support pose endpoints. Neither new branch has established a quality or speed advantage.

| Branch | Lag at confidence .3, four original windows | Lag at confidence .5 | Primary common-support error .3 / .5 |
|---|---|---|---|
| Native | 13, 10, 8, 4 | 13, unknown, unknown, 4 | 1.12808 / 1.14421 |
| Full | 1, 0, 1, 1 | 1, unknown, 1, 1 | .13318 / .13396 |
| DC | 1, 0, 1, 1 | 1, unknown, 1, 1 | .13972 / .14073 |
| SP | 2, 3, 3, 2 | 2, unknown, 3, 2 | .22470 / .22450 |

Windows remain 50–65, 69–81, 80–92 and 99–111. Positive lag means the edited pose occurs later. These lags are local pose-estimator outputs, not proof of semantic action deletion. The confidence thresholds are sensitivity checks, not confidence intervals. No single-arm fallback, new window or wider lag range replaced the frozen endpoint. Unknown results remain unknown.

For the primary window, the common valid support across source and all four methods is 1.00000 at .3 and .953125 at .5, both above the existing .8 gate. The same-frame errors use exactly that shared support and common confidence weights. At .5, four-arm common support in windows 69–81 and 80–92 is only .61538 and .73077; comparisons there cannot satisfy the support gate, even though some individual methods have reliable phase estimates.

## Outside-window checks

These existing bins are supplementary screening, not newly selected primary endpoints. At .3, common-support arm-direction errors are:

| Frames | Common support | Native | Full | DC | SP |
|---|---:|---:|---:|---:|---:|
| 0–46 | 1.00000 | .13693 | .12381 | .12435 | .12917 |
| 47–67 | 1.00000 | 1.03838 | .16039 | .17882 | .29134 |
| 68–140 | .97945 | .47102 | .11729 | .12143 | .25328 |
| 112–140 | 1.00000 | .09703 | .06684 | .07071 | .08279 |
| 0–140 | .98936 | .43256 | .12578 | .13067 | .21432 |

The .5 checks give the same broad ordering. SP's benefit over native is not confined to the primary window, but its errors remain above full/DC in these bins. A pose error curve does not measure identity, background fidelity, temporal flicker or perceptual quality by itself.

## Fixed-frame visual check

Original frames55 and86 were inspected for all branches. Full/DC show the raised-hand/raised-leg event at55 and overhead-arm event at86; their fixed views look close. SP also contains the primary event, while its overhead hands at86 do not precisely match the source spread. The adult male grey-top/dark-trouser edit and gross white-room layout remain visible in all inspected outputs. Motion blur and hand/face details limit stronger judgments. There is no obvious gross background collapse at these views, but this is **only a limited fixed-frame layout/edit-presence check**, not a full-video quality pass or exact-identity certification. Individual reviews are bound to their video hashes in `pilot/*.quality_review.json`.

## Integrity and interpretation

The R3 native passive-recording run is an exact replay of the earlier .9 native: actual inputs/noise match; all five common video/audio snapshots were loaded and checked for tensor equality; 141/141 decoded RGB frames and timing match. See `replication/native_replay_complete_gate.json` and its underlying tensor/RGB reports. This validates the passive baseline; it is not another seed.

The .41 R2 dynamic branch did not demonstrate the same primary repair. Preserve that negative result. The R2/R3 actual-input audit also finds different decoded input-video, prepared video/VAE and conditioning-embedding hashes, despite matched prompt, noise signature and target geometry. Thus a cross-round contrast must not be attributed solely to GPU arithmetic. Within-round comparisons remain the appropriate causal comparison. The subsequent read-only producer audit in R2 `analysis/input_runtime_difference/REPORT.txt` localizes the earliest decoded-input difference to the PyAV YUV-to-RGB conversion path: identical source MP4 and 141-frame native YUV streams, different float-RGB streams, with a same-.41 PyAV16 CPU control reproducing the .9 RGB hash. This does not explain the entire DC outcome difference: even the identity-image VAE latent differs despite matching prepared image RGB. Our `replication/input_runtime_difference_supplement.json` adds the final SP input/noise check to that earlier report’s three-arm R3 scope, without editing its files.

DC and SP share the intended temporal and spatial marginal properties reviewed by the theory lane, but their distributions differ. SP succeeding on the primary event means the DC signed-coefficient construction is not necessary for this case. SP not outperforming DC does not prove nonnegativity is harmful in general. Full/DC similarity does not establish pure motion extraction, appearance disentanglement or general robustness. Actual same-QKV component-probe integrity is documented separately; pose scores do not replace that audit.

## Cost and research decision

Actual whole-prompt wall seconds are native1457.729, full1473.221, DC1480.007 and SP1495.689. These include graph work, cache/model effects and passive capture/I/O. They are descriptive run times, not a controlled speed benchmark; neither DC nor SP has demonstrated a speed gain here.

The defensible result is useful local-event timing correction with multiple implementations, plus a negative comparison for SP superiority and a cross-round limitation for DC. Novelty and utility are separate questions. This single case does not establish a publishable new architecture, but it does justify targeted efficiency or complementary-quality tests; a related prior idea is not itself a reason to discard an empirically useful component. The proposed middle-ten-block depth ablation and target-path representability probe should retain their own predeclared comparison gates and must not be retroactively presented as predictions of this result.

## Reproduction records

- `R3_RUN_INVENTORY.json`: exact run IDs, prompts, producer paths and artifact hashes.
- `compact_summary.json`: frozen four-window results, flags and quality limits.
- `pairs/four_arms_threshold0.3.json` and `.5.json`: all common-support curves and bins.
- `within_round_actual_input_gate.json`: all four actual input/noise checks pass.
- `prompt_walltime_summary.json`: raw successful history timestamps.
- `R3_CPU_COMPLETION.json`: serial CPU completion and archive verification.

No GPU process was started by this evaluator. All formal measurement artifacts and failures were retained; no threshold, source window or operator was changed during evaluation.
