"""Independent research node; does not modify H3Study or any active graph."""
from .nodes import H3DirectionGatedSchedule

NODE_CLASS_MAPPINGS = {"H3DirectionGatedSchedule": H3DirectionGatedSchedule}
NODE_DISPLAY_NAME_MAPPINGS = {"H3DirectionGatedSchedule": "H3 Reference Time Direction Gate (Research)"}
