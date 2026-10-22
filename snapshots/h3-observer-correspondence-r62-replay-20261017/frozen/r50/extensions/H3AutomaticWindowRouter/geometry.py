"""Validated geometry and observation domain; contains no policy thresholds."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Geometry:
    width: int = 1312
    height: int = 736
    frames: int = 141
    fps: int = 24
    valid_frames: int = 141

    def __post_init__(self):
        if any(type(x) is not int for x in
               (self.width, self.height, self.frames, self.fps, self.valid_frames)):
            raise ValueError('geometry fields must be integers')
        if self.width < 32 or self.height < 32 or self.width % 32 or self.height % 32:
            raise ValueError('dimensions must be positive multiples of32')
        if self.frames < 5 or self.frames % 17 != 5 or self.fps != 24:
            raise ValueError('requires H3 17k+5 frame grid at24fps')
        if not 32 <= self.valid_frames <= self.frames:
            raise ValueError('valid observation domain must contain32..frames')

    @property
    def latent_bins(self):
        return ((self.frames - 5) // 17) * 5 + 2

    @property
    def spatial_shape(self):
        return (self.height // 32, self.width // 32)

    @property
    def gain_shape(self):
        return (self.latent_bins, *self.spatial_shape)

    @property
    def frame_rows(self):
        h, w = self.spatial_shape
        return h * w

    @property
    def stream_shapes(self):
        return ((1, 24, self.latent_bins, self.height // 16, self.width // 16),
                (1, 32, 2, round(self.frames / self.fps * 40)))

    @property
    def video_geometry(self):
        return dict(width=self.width, height=self.height, frames=self.frames, fps=self.fps)

    @property
    def domain_record(self):
        return {'schema': 'h3-observation-domain-v1',
                'full_geometry': self.video_geometry,
                'valid_frames_inclusive': [0, self.valid_frames - 1],
                'excluded_padding_frames': list(range(self.valid_frames, self.frames)),
                'timebase': 'original physical frame index/fps; no reindexing',
                'applies_to': ['scale', 'scan', 'lag_matching', 'null_matching', 'common_support']}

    def windows(self):
        for length in (16, 32):
            starts = sorted(set(range(0, self.valid_frames - length + 1, 4)) |
                            {self.valid_frames - length})
            for start in starts:
                yield [start, start + length - 1]

    @classmethod
    def from_case(cls, case):
        g = case['geometry']
        if set(g) != {'width', 'height', 'frames', 'fps'}:
            raise ValueError('unexpected case geometry fields')
        return cls(**g, valid_frames=case['valid_frame_count'])


LEGACY = Geometry()
FLEXIACT = Geometry(width=1152, height=768, frames=158, valid_frames=147)
