"""Opt-in research node; importing does not install or mutate a model."""
# ruff: noqa: N999 -- Comfy custom-node directory follows the existing H3 node naming.

from .adapter import H3PartialRoPE

NODE_CLASS_MAPPINGS = {"H3PartialRoPE": H3PartialRoPE}
NODE_DISPLAY_NAME_MAPPINGS = {"H3PartialRoPE": "H3 partial temporal RoPE (reference branch)"}
