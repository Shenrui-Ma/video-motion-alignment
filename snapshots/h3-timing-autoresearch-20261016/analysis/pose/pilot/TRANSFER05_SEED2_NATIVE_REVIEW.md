# Additional source05 seed reproduces a clear timing delay

The preselected new noise seed2026101312 succeeded as `s05_full_seed2_native_x0` in the isolated transfer runtime. The exact retry prompt is `50e0e2bc-bdda-4805-84ea-c7dbc405e22b`. This is a new noise sample of the same source/identity/configuration, not another deterministic replay of the first seed.

The frozen50–65 window gives combined-arm lag+15 at both confidence thresholds0.3 and0.5; right-arm and wrist-relative features give+16 at both, while left-arm and body give+15. The primary combined-arm best-shift residual is .09356/.09379, with same-frame support1.0/.9844. No ambiguity, coverage or residual gate rejects this primary timing signal.

| Window | Combined-arm lag,0.3 | Combined-arm lag,0.5 | Right-arm lag,0.3 |
|---|---:|---|---:|
| 50–65 | +15 | +15 | +16 |
| 69–81 | +15 | Rejected: insufficient coverage | +15 |
| 80–92 | +16 | +16 | +16 |
| 99–111 | +17 | +17 | +17 |

Unlike the first seed's+13/+10/+8/+4 pattern, this seed retains a roughly15–17frame delay into later events. The right-wrist shoulder crossings at0.3 are64/82/91/123 versus source49/66/76/106. These operational geometric events agree with delayed timing; they do not establish a permanent action omission.

This extends the observed failure to an additional preselected noise seed. It does not estimate general failure prevalence or establish cross-scene generalization. The matching mass intervention is pending; no transfer success is claimed from the baseline alone.

The earlier transfer attempt failed a runtime root guard before sampling and is independently retained under `archive/attempt1_before_root_guard_fix`; it is not a generated-motion failure. The analyzed retry uses the exact successful history and config geometry. CPU evaluation was manually advanced at04:03:16 in a verified primary-inference gap: main phase+ was12/20 with approximately10minutes remaining, no other pose process was active, and the transfer consumer remained waiting. Full details are in `../transfer_manual_native_admission.json` and `../TRANSFER_ATTEMPTS.json`. The later consumer will reuse this pose only when the video hash and full-frame extraction settings match; reuse was independently tested.

Raw output, exact history/config/conditioning/noise/router audit and pose diagnostics are archived under `s05_full_seed2_native_x0_provenance/archive_manifest.json`, retaining the transfer-root origin. The four windows and thresholds were not changed after viewing this seed.
