# R150 active execution

Updated 2026-10-21. Root authorized all selected cases and exact-owner hardware recovery.

- .41 GPU0: `long_0059`, service228449, wrapper228421, attempt `root_r150_long0059_host41_attempt1`; four schedules. Root accepts current low free memory while sampling; react to actual OOM or explicit driver failure. Other UID1011 qwen-tts service stays untouched.
- .9 GPU2: `short_0274`, service23230, wrapper23209, attempt `root_r150_short0274_host9_attempt1`; early and late passed, split in progress. R151 uses GPU3 and is registered as an exact peer.
- .41 GPUs4–7 require reset; old task processes exited, affected CUDA allocations remain unknown. Do not reset GPUs.

Completed R150: blue-book four schedules, red-hair four schedules, alien early and late =10 new videos. The evaluation agent uniquely collects MP4 and small gates.

Qwen recovered three conditions with one model load in238 seconds; process225329 exited and CUDA allocation released. Musk05 matches historical raw embedding SHA. Firefly06 and Sam07 require one new shared-cache Native each. Total planned new videos33.

Prepared and actual target CPU validated:

| case | target | seal | roles |
|---|---|---|---|
| musk05 | .9 GPU2 | ffbf875c7e12c4268ecaa28b8c6d8381e53822c96059a7bd858c140772119b70 | fixed, early, late, split, global_weak |
| firefly06 | .41 GPU0 | 2bc436b7179b908688584ca049078142f75ba27478f2ca525a17be1b16c708ed | native, fixed, early, late, split, global_weak |
| sam07 | .9 GPU3 | 9e38fc0736000dc9e9479633a0287eac5dac1b7fa1e686a8c7039fb741d2d173 | native, fixed, early, late, split, global_weak |

After each predecessor has actual COMPLETE/ROOT_EXIT and exact service/wrapper/CUDA release, run the prepared `producer/launch_case.py --execute --seal HASH --attempt NAME --predecessor-root ROOT --predecessor-attempt NAME` under that target root. Helpers perform fresh capacity, GPU and exact peer checks. Next: alien→Musk05; handkerchief→Firefly06. Sam07 goes to .9 GPU3 after the actual R151 six-video plus six-MF release, using `--mf-release-sha` instead of a video predecessor. Root may insert short R150 MF batches in that transition gap; honor their actual GPU release before Sam07. Its original GPU0 package remains unstarted.

Watchers use45-second intervals and record per-step duration. Current local tool sessions: hand70650, alien51267. No additional sampling tests, backend comparisons or online VAE/DWPose observers.

Scientific settings: original prompt, seed, original AV noise, reference caches,20Euler steps, phase0; same-bin correction. early0–8, late11–19, split0–3+15–19, global all20 alpha0.25/all valid physical frames. New fixed6–14 for legacy dance tasks. Optional native has empty schedule and same recovered conditioning.
