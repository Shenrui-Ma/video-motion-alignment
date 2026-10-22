"""Standalone experimental coverage node; import installs no model patches."""
from .routing import CoverageConfig, CoverageResult, solve_temporal_coverage
from .nodes import H3TemporalCoverageBlend

NODE_CLASS_MAPPINGS = {"H3TemporalCoverageBlend": H3TemporalCoverageBlend}
NODE_DISPLAY_NAME_MAPPINGS = {"H3TemporalCoverageBlend": "H3 Reference Time Coverage (Research)"}

__all__ = ["CoverageConfig", "CoverageResult", "solve_temporal_coverage",
           "H3TemporalCoverageBlend", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
