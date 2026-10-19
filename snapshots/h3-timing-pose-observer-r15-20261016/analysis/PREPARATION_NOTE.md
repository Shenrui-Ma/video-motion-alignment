R15 preparation, 2026-10-16. No GPU was launched by this agent.

The first CPU adapter test rejected the real R10 branch schema because the initial locator had retained only selected metadata fields while the payload also contains raw_stream_signatures. The guard was corrected to require exactly the selected fields plus raw_stream_signatures, check all against the complete frozen source audit, and independently verify raw and normalized tensor signatures. The input/runtime/sampling files were not changed. This was a preparation-schema error, not a model or scientific failure.
