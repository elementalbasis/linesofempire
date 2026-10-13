import math
import numpy as np

from common import normalize


# These are deliberately kept here for now so border.py is self-contained.
# Move them into config.py once the generator has settled.
DEFAULT_NODE_SPACING_MIN = math.radians(1.2)
DEFAULT_NODE_SPACING_MAX = math.radians(1.8)

DEFAULT_AMPLITUDE_MIN = 0.07
DEFAULT_AMPLITUDE_MAX = 0.14

DEFAULT_MIN_SEGMENTS = 2
DEFAULT_SMOOTHING_PASSES = 1
DEFAULT_ENDPOINT_ENVELOPE_POWER = 1.4


class Border:
    def __init__(
        self,
        region_a,
        region_b,
        start,
        end,
        nodes=None,
        frozen=False,
        reroll_index=0,
    ):
        self.region_ids = tuple(sorted((region_a, region_b)))

        self.start = normalize(np.asarray(start, dtype=np.float64))
        self.end = normalize(np.asarray(end, dtype=np.float64))

        if nodes is None:
            self.nodes = np.asarray(
                [
                    (0.0, 0.0),
                    (1.0, 0.0),
                ],
                dtype=np.float64,
            )
        else:
            self.nodes = np.asarray(nodes, dtype=np.float64)

        self.frozen = frozen
        self.reroll_index = reroll_index

    @property
    def key(self):
        return self.region_ids

    @property
    def angular_length(self):
        dot = np.clip(np.dot(self.start, self.end), -1.0, 1.0)
        return math.acos(dot)

    @property
    def vertices(self):
        return border_vertices(
            self.start,
            self.end,
            self.nodes,
        )

    def set_endpoints(self, start, end):
        self.start = normalize(np.asarray(start, dtype=np.float64))
        self.end = normalize(np.asarray(end, dtype=np.float64))

    def set_nodes(self, nodes):
        self.nodes = np.asarray(nodes, dtype=np.float64)

    def to_dict(self):
        return {
            'regions': list(self.region_ids),
            'start': self.start.tolist(),
            'end': self.end.tolist(),
            'nodes': self.nodes.tolist(),
            'frozen': self.frozen,
            'reroll_index': self.reroll_index,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            region_a=data['regions'][0],
            region_b=data['regions'][1],
            start=data['start'],
            end=data['end'],
            nodes=data['nodes'],
            frozen=data.get('frozen', False),
            reroll_index=data.get('reroll_index', 0),
        )


def border_segment_count(
    start,
    end,
    rng,
    spacing_min=DEFAULT_NODE_SPACING_MIN,
    spacing_max=DEFAULT_NODE_SPACING_MAX,
    min_segments=DEFAULT_MIN_SEGMENTS,
):
    start = normalize(np.asarray(start, dtype=np.float64))
    end = normalize(np.asarray(end, dtype=np.float64))

    dot = np.clip(np.dot(start, end), -1.0, 1.0)
    length = math.acos(dot)

    spacing = rng.uniform(spacing_min, spacing_max)

    return max(
        min_segments,
        round(length / spacing),
    )


def generate_land_border(
    border,
    rng=None,
    spacing_min=DEFAULT_NODE_SPACING_MIN,
    spacing_max=DEFAULT_NODE_SPACING_MAX,
    amplitude_min=DEFAULT_AMPLITUDE_MIN,
    amplitude_max=DEFAULT_AMPLITUDE_MAX,
    min_segments=DEFAULT_MIN_SEGMENTS,
    smoothing_passes=DEFAULT_SMOOTHING_PASSES,
    endpoint_envelope_power=DEFAULT_ENDPOINT_ENVELOPE_POWER,
):
    if border.frozen:
        return border

    if rng is None:
        rng = np.random.default_rng()

    segments = border_segment_count(
        border.start,
        border.end,
        rng,
        spacing_min=spacing_min,
        spacing_max=spacing_max,
        min_segments=min_segments,
    )

    # Slightly irregular positive spacing keeps the path moving monotonically
    # from one endpoint to the other while avoiding visibly uniform sampling.
    steps = rng.uniform(
        0.7,
        1.3,
        size=segments,
    )

    t = np.concatenate((
        [0.0],
        np.cumsum(steps),
    ))
    t /= t[-1]

    # A cumulative random walk produces broad bends rather than independent
    # point-to-point noise.
    offset = np.zeros(segments + 1, dtype=np.float64)
    offset[1:] = np.cumsum(
        rng.normal(
            0.0,
            1.0,
            size=segments,
        )
    )

    # Brownian-bridge correction forces the random walk back to zero at the
    # far endpoint without destroying its larger-scale shape.
    offset -= offset[-1] * t
    offset[0] = 0.0
    offset[-1] = 0.0

    for _ in range(smoothing_passes):
        old = offset.copy()
        offset[1:-1] = (
            0.25 * old[:-2]
            + 0.50 * old[1:-1]
            + 0.25 * old[2:]
        )

    # Suppress displacement near shared Voronoi vertices so several borders
    # can meet cleanly without explosive kinks around the junction.
    envelope = np.sin(np.pi * t) ** endpoint_envelope_power
    offset *= envelope

    maximum = np.max(np.abs(offset))
    if maximum > 0.0:
        amplitude = rng.uniform(
            amplitude_min,
            amplitude_max,
        )
        offset *= amplitude / maximum

    border.nodes = np.column_stack((
        t,
        offset,
    ))

    border.reroll_index += 1

    return border


def border_vertices(start, end, nodes):
    start = normalize(np.asarray(start, dtype=np.float64))
    end = normalize(np.asarray(end, dtype=np.float64))
    nodes = np.asarray(nodes, dtype=np.float64)

    dot = np.clip(np.dot(start, end), -1.0, 1.0)
    theta = math.acos(dot)

    if theta == 0.0:
        return np.repeat(
            start[None, :],
            len(nodes),
            axis=0,
        ).astype('f4')

    sin_theta = math.sin(theta)

    # Normal to the great-circle plane. Since every point on the great-circle
    # arc is perpendicular to this vector, it is also a valid tangent-space
    # direction for the border's sideways displacement.
    sideways = normalize(np.cross(start, end))

    vertices = []

    for t, offset in nodes:
        if abs(sin_theta) < 1e-12:
            # Extremely close to the antipodal case. Linear interpolation is
            # only a fallback; normal Voronoi edges should not reach this.
            centerline = normalize(
                (1.0 - t) * start
                + t * end
            )
        else:
            centerline = (
                math.sin((1.0 - t) * theta) / sin_theta * start
                + math.sin(t * theta) / sin_theta * end
            )
            centerline = normalize(centerline)

        # `offset` is stored as a fraction of the source edge length, so its
        # physical angular displacement scales naturally with border length.
        displacement = offset * theta

        point = (
            math.cos(displacement) * centerline
            + math.sin(displacement) * sideways
        )

        vertices.append(normalize(point))

    return np.asarray(vertices, dtype='f4')
