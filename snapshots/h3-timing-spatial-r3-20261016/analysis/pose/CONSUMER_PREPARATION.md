# R3 CPU evaluation preparation

Prepared only; no monitor or CPU process launched. The existing R2 consumer remains the sole pose consumer.

`consumer_r3.py` adapts the validated R2 intake to the .9 R3 producer and `H3SpatialMarginalRouter`. It rejects benchmark IDs, requires the exact successful controller history and identical stored graph, resolves the output from SaveVideo history, verifies the remote/local MP4 hash and geometry, and uses the unchanged frozen pose/timing tools with source05's original four windows and both confidence thresholds. All failures remain archived. It never contacts a Comfy port, submits inference, installs dependencies, or enables CUDA.

The optional `--intake-only` mode only copies exact successful MP4/history/audit material. It does not run pose. To evaluate, omit that option only after the parent allocates a serial CPU slot. No second waiting CPU consumer should run while R2 can launch pose. The remote process guard rejects any active pose or timing process; this is a guard, not permission to race two consumers.

Four formal runs: native, full_6to14, dynamic_6to14 and spatial_6to14. The benchmark is excluded. Same R3 native/full controls remain necessary; old output is not automatically interchangeable. The config SHA256 values in preparation.json were read-only checked against the actual .9 producer copies.
