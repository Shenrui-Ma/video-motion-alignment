R34: fixed early global Full pulse, design only

Question
On source40372/Sam/seed2026101701, test a simple Full pulse at zero-based denoising index4 (the fifth Euler call), then continue Native. Index4 is taken from earlier R27 development evidence and is frozen before the R32 outcome. The pulse covers the whole physical video0..140, all42 nominal bins, all spatial target-video query rows, all50 blocks, alpha1/radius0. It does not use source risk, online pose, automatic candidates or final metrics to decide a window or step.

Execution contract
Reuse the R33 same-state Native→optionalFull transaction shape in an independent implementation:20 Native predictions plus one Full prediction atindex4,21NFE,20Eulerupdates,20callbacks,1050blockcalls and50routedblockcalls. Compute both branches from identical current input/conditions/sigmas, chooseFull for the single update at4. Save all20chosen endpoints and actualfinal, all21branch endpoints and input4. No online observations. Do not optimize to a20NFE directFull implementation under this protocol.

Source40372 has actual packed length87361, with6729text+950portrait+39606reference-video+470audio+39606target-video rows. Each time bin contains943spatialrows. The inherited [1,4,4,4,4] span mapping totals141frames across42bins; all42bins cover0..140. These are positional bins, not an asserted exact VAE receptive field. The old87592 layout and source05 windows must not be copied.

Comparators
R26 same-source Native; R29 globalFull6..14; R32 frozen automatic window/schedule policy; R34 earlyglobalpulse. Actual input/noise/layout/model and prefix gates remain required. The six R29/R32 parent JSON artifacts currently match bytewise. R26 has actual21endpoint files; read0..4 for bothAV streams before allowing R34 intervention. Only chosen0..3 and Native4 can match historicalNative; all future states diverge after choosingFull4. R26's full historical postaugmentationtree and packedinput4 were not saved; code/seed plusclean tensors and actualprefix constrain this gap without pretending the missing tree was measured.

Outcome contract
Keep the inherited exploratory40..55 descriptor, all186 overlapping whole-clipscan rows, frozen two confidence thresholds and UNKNOWN gates, four-arm andAuto/pulse common support, original0/35/70/105/140images and full141frame clip. Never evaluate solely on automatically chosen windows. A pulse that matchesAuto makes added automatic-policy benefit unestablished here; anAuto advantage is a single-case system-level result, with support/schedule/dose differences retained. Ghost/identity/visibility limits are separate fromposeerror.

Necessity and boundary
This is a necessary simple strong baseline because current evidence permits a small early perturbation to improve later motion without a precise detector. It provides a falsifiable alternative to online selection. It is not equal intervention dose: R34 writes39606queryrows perlayer once (1,980,300query-row-blocks), R29 does thisnine times, andR32 uses actualdynamic unions andK. Native reference-group mass depends on eachquery/state; alpha1 is not equal mass acrossarms. Success againstR34 would not by itself isolate automatic scheduling, automatic window selection, or a novel architecture.

No runtime files, graph, code copies, dependencies, model operations or GPUlaunch are part of this design. Root schedules later. The PROTOCOL and COMPARABILITY documents are fixed with SHA256 inFREEZE.
