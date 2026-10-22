R70 CPU consumer

Only consume after root checks actual child exit and absent CUDA allocation.
verify_result.py --run <completed outputs/attempt1> --exit-receipt <root receipt> --out <new analysis/consumer/attempt1>
make_visual.py --run <local completed outputs/attempt1> --verified <VERIFIED.json> --out <new visual dir>

The verifier checks completed 3 encode + 6 decode / 0 DiT, fallback count zero, exact PID release receipt, producer FREEZE SHA, 8 video hashes and actual 158-frame probes, encoded latent hashes, exact coordinate maps and independent reduction checks. Two CPU tests protect release requirements and the intersection of three validity domains.

ERROR_TABLE.csv reports float RGB mean absolute errors. The common valid mask intersects input/output valid147, RGB domain and nominal latent-center domain. Extra consumer regions separate cross-17 latent interpolation/source changes, decoder overlap, and the 144 timestamps valid for all three maps. Coordinate validity does not establish valid semantic matching. Maps with different target content are not ranked as method quality by RGB error.

Visual presentation keeps every output frame and aspect ratio. Fixed six times are 0,.5,1,1.5,2,2.5 s; fixed boundary frames are16,17,18,33,34,35. Additional largest-error frames are explicitly identified as selected by photometric error. Latent/RGB operators are compared against the same direct RGB target; identity is shown separately. No timing-accuracy claims follow from these image errors.

Offline phi was fitted from the final Native output and is applied to index6 x0 only for operator feasibility. It is neither an online detector nor a prospective algorithm evaluation.
