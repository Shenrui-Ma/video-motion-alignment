# Call6-start routing restores the selected target phase

The formal run `s05_full_seed1_mass_late6_x0` succeeded, with exact-history prompt `b55baafb-8213-480b-a79a-09996c86cbc4`. Its 141-frame, 1312×736, 24fps MP4 is archived with SHA256 `a125d806a7ea0188cf3cb2447377221d510b37b6ea3615c58ebd76b5c7636c25`. The pose extractor selected one person in all141 frames, with no missing, multiple or ambiguous person selection.

For the frozen primary window50–65, combined-arm direction gives **+1 frame at both confidence0.3 and0.5**, and right-arm direction independently gives+1/+1. Left-arm and body features give0/0. Combined-arm same-frame errors are .13313/.13445 and best-shift residuals .10931/.11032, with same-frame coverage1.0/.9844. This meets the previously registered direction-based complete-target-alignment region of±2frames for this selected run, compared with native+13/+13 and call11-start mass+11/+12.

This is not an all-feature consensus claim: primary wrist-relative lag is formally rejected at both thresholds. Its numerical best is+1, but the shift improves an already low same-frame error(.15214 at0.3) by less than1%, below the frozen5% nonzero-shift reliability rule. This abstention remains in the result; it is not converted into a reliable zero or+1 lag. The right-wrist geometric events nevertheless occur at50/67/76/106 versus source49/66/76/106 and native63/77/85/108.

| Frozen window | Native lag,0.3 | Call11 mass lag,0.3 | Call6 mass lag,0.3 | All-step mass lag,0.3 |
|---|---:|---:|---:|---:|
| 50–65 | +13 | +11 | +1 | 0 |
| 69–81 | +10 | +10 | 0 | −1 |
| 80–92 | +8 | +8 | +1 | 0 |
| 99–111 | +4 | +4 | +1 | −1 |

At confidence0.5, window69–81 remains rejected because combined and right-arm same-frame coverage is .7308; the other three combined-arm windows remain+1. At0.3 this middle window is usable but imperfect: combined residual .4001 and right-arm residual .4887. Thus near-zero lag does not establish exact pose reproduction.

The fixed55/86 frame screen shows the expected raised-arm positions, gray long sleeves/dark trousers and the white room/curtain/bench. It does not show the seed2 black-background failure. This is a limited appearance sanity check, not full identity recognition or a comprehensive quality evaluation.

Root's `audit/late6_preintervention_tensor_equality.json` was read and confirms exact native/call6 video AND audio tensors at x0_step005. The change therefore begins after that captured common state. On native-versus-call6 shared support at0.3, full-clip error falls from .4412 to .1327, the after-bin segment68–140 from .4843 to .1253, and the tail112–140 from .0970 to .0658. The all-141 same-frame common-support screen is preserved in `../full_support/through_late6/`, including per-frame curves and the original pre/bin/post/tail segments. It shows no new broad arm-error degradation in those aggregate regions, but these ancillary errors are not a significance test or a substitute for visual-quality evaluation.

The supported inference is narrow: for this fixed same-bin routing actuator, starting at call6 can repair this selected timing error while starting at call11 did not. This brackets a controllability difference between two tested schedules; it does not locate an exact irreversible transition, prove a novel routing architecture, or demonstrate online feedback. The frozen combined-arm observer was unknown at step005, and steps6–9 were not sampled. A known earlier left-arm signal must not be retrospectively substituted for the registered combined-arm trigger.

Evidence: `LATE6_PRIMARY_DECISION.json`, the exact raw-video archive manifest, all frozen timing JSONs, the causal tensor artifact, and `../full_support/through_late6/`.
