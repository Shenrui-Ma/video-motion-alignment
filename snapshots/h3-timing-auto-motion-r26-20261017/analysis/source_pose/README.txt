R26 source-only automatic clip selection

Owner scope: assets/prepared, analysis/source_pose, configs/source_selection*.
No model inference, generated output, or manual event window is used for selection.

Order: protocol and extraction/ranking code freeze -> complete source pose -> exhaustive 141-frame sliding selection -> exact-frame export -> fixed checkpoint visibility review. Visual review reports tracking limits; it does not change selected start or threshold.

Each source is first converted to a complete 24 fps, 1312x736 aspect-fit/padded timeline. Every candidate start with 141 remaining frames is scored. Primary support is raw pose confidence .3; .5 is report-only. Eligibility prioritizes shoulders/hips and both arms, then both legs. The activity proxy counts separated signed bone-direction reversals across fixed +/-4-frame neighborhoods after 3-frame unit-direction smoothing. It is not semantic action classification. All scores, rejects, raw event candidates, and all three sources remain archived, including UNKNOWN_support.

Selected clips are lossless YUV trims from that prepared full timeline. Export additionally checks every decoded RGB frame and the time base. Derived selected pose JSON keeps full-source person-tracking context; the tracker was not reinitialized at clip start. Its raw model provenance is unchanged. A separately reinitialized clip run might choose another person; downstream users must preserve or explicitly record that difference.

Source-selection constants are frozen in configs/source_selection_protocol.json and source_selection_freeze.json. Export and contact sheets are packaging-only additions and do not change ranking. Selected source pose can support later diagnostics, but these new source clips do not establish that H3 fails, that its output has a time lag, or that an intervention works.
