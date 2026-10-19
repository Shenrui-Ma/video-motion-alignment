# Ordinary same-bin hard masking also fixes the selected timing failure

Formal run `s05_full_seed1_hard_x0` succeeded (prompt `ae6175e7-531a-4025-9ca8-e9a924fd7057`), with the exact history output `s05_full_seed1_hard_x0_00001_.mp4`: 141 frames, 1312×736 pixels, 24fps. Runtime was25:45. Its ordinary hard route was active in all1000 intended block calls; config/audit/history and the raw video are archived with hashes.

The primary50–65 window has zero both-arm and right-arm lag at confidence0.3 and0.5. Its four-window both-arm lags at0.3 are0/−1/0/−1, the same phase pattern as all-steps mass routing. The right-arm69–81 estimate is rejected because residual error remains above0.5; confidence0.5 also rejects the low-coverage middle window. These failures remain in the data.

This is a negative result for a claim that mass preservation is necessary for the observed rescue. Ordinary hard temporal restriction already suffices in this source/seed. It does not establish that the two operations are identical, or rule out benefits of conserving mass in other settings.

## Same-support comparisons

Source, native, mass, hard and archived x3 use identical valid joint-frame support and shared minimum-confidence weights within each row. Unit arm-bone errors are not calibrated visual-quality scores.

| Window, confidence0.3 | Coverage | Native | Mass | Hard | x3 |
|---|---:|---:|---:|---:|---:|
| 50–65 | 100% | 1.125694 | .098471 | .097245 | .139353 |
| 69–81 | 94.2% | 1.263788 | .524877 | .526467 | .623327 |
| 80–92 | 96.2% | 1.137237 | .107437 | .105586 | .119169 |
| 99–111 | 100% | .410815 | .095476 | .110282 | .116031 |

At confidence0.5, the primary row has96.9% coverage and native/mass/hard/x3 errors1.135368/.096683/.095149/.136354. The middle two common-support rows fall below80% coverage and are retained but not treated as robust comparisons. Mass is slightly better in the final window; hard is slightly better in the first and third at0.3. These small differences from a single selected case support neither statistical superiority nor a mass-specific mechanism claim.

Right-wrist geometric crossing frames in hard are48/66/75/104, compared with source49/66/76/106 and native63/77/85/108. These are operational 2D shoulder-crossing events, not semantic hand annotations.

## Preservation and propagation checks

The posthoc full-clip screen compares the same named method set (including the duplicate phase-zero control). At0.3,141-frame errors are native .43314, mass .14583, hard .15250 and x3 .17107 on99.1% common support. Before the intervention bin, frames0–46 are .13525/.14098/.14986/.15538; in the tail112–140 they are .09711/.11648/.11799/.11253. Hence all interventions have some measured peripheral cost on this already-accurate part, despite much larger improvement in the targeted portion. Small pose-score changes alone do not establish perceptual degradation. The0.5 full-clip comparison has the same broad outcome.

All141 hard frames have one selected person, with zero missing-person, multiple-person or ambiguous-selection frames. Fixed overlays55 and86 were inspected. Major-limb skeletons match visible raised-arm/bent-leg and overhead-arm poses. Gray long sleeves, dark trousers, short dark hair, room layout and borders remain; no source-outfit reversion is apparent at these points. This is a limited appearance sanity check, not a validated identity score or full-video hand/flicker assessment.

## Exact same-input mass comparison

Read-only implementation verification of `extensions/H3TemporalRouter/core.py` confirms that hard routing mixes the aligned reference subset with the explicit complementary key set using their LSEs. Let the original reference-group mass be m and the aligned subset’s conditional share within that group be s. For the same Q/K/V, hard routing produces reference-group mass m*s/(1-m+m*s), which is at most m. The retained aligned keys and non-reference keys each gain individual probability after the deleted off-time keys are removed, while the reference group as a whole loses probability. Mass-preserving routing assigns the aligned subset total mass m, at least the hard route's reference total.

Therefore hard is not a "stronger reference mass" operation. Its successful full-schedule repair shows that increasing total reference probability is not necessary for this observed effect. It still does not prove which particular off-time correspondence caused the original lag. This inequality concerns a single common-input attention evaluation; separately generated trajectories have different Q/K/V and cannot be compared by treating their logged mass means as a common-input experiment.

## Consequence for the research claim

The useful demonstrated effect is a controlled temporal-reference intervention on a selected failure, with hard masking as a strong ordinary baseline. Do not present group-mass conservation as the discovered innovation or a necessary ingredient. A proposed phase-specific actuator or late intervention must demonstrate its own distinctive effect and limits. No result here demonstrates an online controller, automatic event localization, user-intended motion-edit handling or cross-case generalization.

Artifacts: `full_native_mass_hard_x3_threshold0.3_common_support.json` and0.5; `../full_support/native_mass_x3_zero_hard/` full curves and pairwise reports; `s05_full_seed1_hard_x0_provenance/archive_manifest.json`. Raw MP4 SHA256: `ce4aa4ccb7bf33739fb114138bbb0906baab6264ce67d35b961666a2051eb51d`.
