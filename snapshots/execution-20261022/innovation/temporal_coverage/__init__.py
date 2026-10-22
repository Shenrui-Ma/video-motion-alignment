"""Standalone experimental temporal coverage; importing installs no patches."""

from .routing import CoverageConfig, CoverageResult, solve_temporal_coverage

__all__ = ["CoverageConfig", "CoverageResult", "solve_temporal_coverage"]
