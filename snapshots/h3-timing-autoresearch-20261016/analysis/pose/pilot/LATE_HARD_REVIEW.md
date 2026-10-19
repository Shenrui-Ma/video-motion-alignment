# Call11-start hard routing also leaves the selected phase error

The formal `s05_full_seed1_hard_late11_x0` run succeeded under prompt `9380db38-8790-444d-934c-a53699e3ca12`. Its exact saved141-frame1312×736/24fps MP4 has SHA256 `3dd11dbfe402b02802326a2a199dfe0e50574a17665f2cbe4ea312b17c410230`; raw video, history, graph, audits and CPU pose are archived.

The frozen primary50–65 combined-arm lag remains **+13/+12 frames** at confidence0.3/0.5, with right-arm+12/+12, wrist-relative+12/+12 and body+13/+13. The shifted combined-arm residual is .21122/.20675; same-frame errors .98430/.98757 and coverage1.0/.875. These reliable nonzero lags fail both the±2 complete-alignment and≥4frame partial-improvement gates relative to native+13/+13. Classification is **no_demonstrated_late_control**.

At0.3 the original four combined-arm windows are+13/+10/+8/+4, essentially native-like. At0.5 the69–81 best-shift coverage(.6731) is insufficient despite adequate same-frame coverage(.8077);80–92 same-frame coverage(.7692) is insufficient. These two combined-arm lags remain rejected. Right-arm third-window+8 and final-window+4 remain reliable. Right-wrist events64/77/85/108 at0.3 are also near native63/77/85/108, versus source49/66/76/106.

Fixed55/86 frames retain the gray clothes and white room. Frame55 still has hands forward near the torso rather than the source raised-arm posture. This is a limited edit/pose sanity check, not a complete identity or video-quality evaluation. All141 frames contain one selected person without missing/multiple/ambiguous selection.

Root's saved `audit/hard_late11_preintervention_tensor_equality.json` was read: native and this run have bitwise-equal video and audio tensors at both x0_step005 and010. The causal state before starting call11 is therefore controlled. Actual sigma scheduling is the same shifted video schedule as the other runs; call11 does not mean a generic low-noise terminal regime.

On paired native/hard-late shared support, whole-clip arm error slightly improves .43536→.41871 at0.3, but after-bin68–140 slightly worsens .48338→.48627. Such small aggregate pose changes do not remove the clear primary delay. Full per-frame common-support curves and both thresholds are preserved in `../full_support/through_latehard/`.

At identical Q/K/V, the hard mask removes nonaligned reference keys and changes total reference mass from m to m*s/(1−m+m*s), which is at most m. It must not be described as a stronger reference-mass intervention than native. This result compares normalization/mixing choices: neither tested call11-start mass preservation nor hard masking adequately repairs this case, whereas the full-step versions and call6-start mass do. It does not establish universal late irreversibility or a new architecture. The separately registered equal-nine-calls6–14 experiment can distinguish early-window placement from simply making more intervention calls; it does not equalize sigma-weighted dose.

Evidence: `LATE_HARD_PRIMARY_DECISION.json`, exact-history archive, preintervention tensor audit and `../full_support/through_latehard/`.
