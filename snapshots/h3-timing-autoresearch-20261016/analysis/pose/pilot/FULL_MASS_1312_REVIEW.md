# Original-resolution mass-preserving same-bin routing: single-case improvement

Formal run `s05_full_seed1_mass_x0` completed successfully (prompt `986c45be-832b-4a61-b8a1-217f6e64cae4`). The actual output recorded by history is `s05_full_seed1_mass_x0_00001_.mp4`,1312×736,141frames,24fps, matching the config. Runtime was24:54. Exact raw video and all audit/pose files are archived locally with manifest hashes.

The primary50–65 source window improves from native+13frame delay to0frame delay in both-arm and right-arm direction at both confidence thresholds0.3 and0.5. This supports a controlled intervention effect on the selected failure case. It does not establish novelty, generalization or superiority over all existing guidance methods.

## Phase diagnostics

| Window | Native both-arm lag (0.3) | Same-bin mass lag (0.3) | Same-bin mass right-arm lag (0.3) |
|---|---:|---:|---|
| 50–65 | +13 | 0 | 0 |
| 69–81 | +10 | −1 | Rejected: residual pose difference remains large |
| 80–92 | +8 | 0 | 0 |
| 99–111 | +4 | −1 | −1 |

At0.5, the first-window zero lag and later0/−1lags remain. The69–81 window rejects due to coverage. The right-arm residual minimum in69–81 at0.3 has error0.500526, above the frozen0.5 residual gate; it must not be characterized as purely a one-frame phase error.

Right-wrist geometric crossing frames are48/66/75/105, compared with source49/66/76/106 and native63/77/85/108. These operational threshold events corroborate improved timing, without claiming semantic hand annotations or that an irreversibly missing action was restored.

## Same-frame errors on common support

Each row uses exactly the intersection of valid source/native/mass/x3 joint-frame observations and shared minimum-confidence weights. An arm cannot improve its score by removing difficult joints from its denominator. Errors are weighted Euclidean differences of unit bone-direction vectors, not pixel MSE or a calibrated perceptual-quality score.

| Window, confidence0.3 | Common coverage | Native both-arm | Same-bin mass | Archived x3 |
|---|---:|---:|---:|---:|
| 50–65 | 100% | 1.125913 | 0.098553 | 0.139414 |
| 69–81 | 94.2% | 1.260585 | 0.525242 | 0.623189 |
| 80–92 | 96.2% | 1.137190 | 0.107414 | 0.119150 |
| 99–111 | 100% | 0.410964 | 0.095428 | 0.115996 |

The primary right-arm comparison is1.262355 /0.129983 /0.214787 (native/mass/x3), with100% common coverage. At0.5, primary both-arm values are1.135587 /0.096768 /0.136417 and right-arm1.290424 /0.126395 /0.210936, both with96.9% coverage. Middle-window0.5 support is insufficient for some comparisons and is retained as such in JSON; these rows are not counted as robust wins.

Archived x3 config was checked directly: the reference-event enhancement uses factor3 and the same50–65frame interval. Its ordinary reference-logit enhancement is an important competitor, not an absent baseline. The new mass result is numerically better in these exploratory same-frame measurements, but this is one selected seed/case, without a significance test or a held-out benchmark.

## Fixed-frame appearance and measurement checks

All141frames have one selected person, with zero missing-person, multiple-person or selection-ambiguity frames. Overlays55/63/86/105 were inspected. Detected skeletons agree with visible major limbs. The gray long-sleeved top, dark trousers and short dark hair remain in these frames, with the room and borders retained; the edit has not visibly reverted to the source outfit at these inspection points. Frame55 now shows the raised arm/bent-leg pose, and frame86 the overhead-arm pose.

This is a limited appearance/pose sanity check. It is not a validated identity score, full-video flicker check, comprehensive hand-quality judgment or proof that source visual details never leak.

## Interpretation and necessary controls

- This is a positive discovery result for the selected known failure. The untouched1024correct-case pair is separately retained and must not be mixed into a rescue success rate.
- Hard same-frame masking must be tested. If ordinary hard masking produces the same improvement without worse editing quality, the evidence does not isolate a benefit of conserving reference attention mass.
- Same-input attention-mass conservation is an algebraic property of the operation, not a new mathematical contribution or proof that an entire generated trajectory preserves native attention mass.
- Signed temporal perturbation controls, posthoc retiming, further seeds and a second source remain necessary to distinguish a phase mechanism from generic stronger motion copying.
- The intervention affects later windows too, although the targeted query interval is50–65. Temporal network coupling means a locally specified intervention is not automatically a spatially/temporally isolated effect.
- These results establish neither automatic detection of an action omission nor a working feedback controller. The separate native x0 observation test and the static mass intervention do not together constitute an online closed loop.

Artifacts: `full_native_mass_x3_threshold0.3_common_support.json` and0.5 counterpart retain all common-support observations; per-run `.timing.json` retains complete lag curves and rejection reasons. `s05_full_seed1_mass_x0_provenance/archive_manifest.json` records the exact raw MP4 SHA256 `2be7a147dec0940e8ac93e2d3d56ea28335763eac20eaabdcd2e3eb6d7a8907a` and copied audit files. The sealed service stopped between polling intervals; the watcher consumed the controller's exact persisted successful history, with the same geometry validation, rather than guessing an MP4 filename.
