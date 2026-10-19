# R10: paired native/Full endpoint readouts

The full replay gate passed: actual inputs/noise, all eight archived parent selected endpoints plus final video/audio tensors, and all141 decoded RGB frames/timebase agree with R3 Full. This adds diagnostic observations, not a new efficacy sample.

Indices are zero-based physical Euler steps. Values below are the frozen internal latent-reader lags, not independent pose estimates. A dash means that branch or readout was not evaluated; an unknown would be retained explicitly.

| Physical index | Native lag (frames) | Full lag (frames) | Chosen branch |
|---:|---:|---:|---|
| 0 | — | — | native |
| 1 | — | — | native |
| 2 | — | — | native |
| 3 | — | — | native |
| 4 | — | — | native |
| 5 | 10 | — | native |
| 6 | 10 | 0 | full |
| 7 | 6 | 0 | full |
| 8 | 3 | 0 | full |
| 9 | 3 | 0 | full |
| 10 | 2 | 0 | full |
| 11 | 1 | 0 | full |
| 12 | 0 | 0 | full |
| 13 | 0 | 0 | full |
| 14 | 0 | 0 | full |
| 15 | 0 | — | native |
| 16 | 0 | — | native |
| 17 | 0 | — | native |
| 18 | 0 | — | native |
| 19 | 0 | — | native |

Native and Full at indices6–14 use the same current state, sigma, conditions and random seed. The sampler always takes Full there; the extra native probes do not update state. Outside that interval only native is evaluated. Endpoint differences do not establish persistent latent correction or justify stopping by themselves.

Recorded:29 model forwards,20 Euler updates,20 callbacks,450 routed blocks; whole prompt 2286.631s. Timing is recorded without a speed diagnosis.

Final pose is inherited only through the exact141-frame replay gate. No DWPose rerun, threshold change, model change or automatic fallback experiment was performed.
