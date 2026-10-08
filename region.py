import numpy as np
import math

import config
from common import normalize, recursively_subdivide_triangle

class Region:
    def __init__(self, region_id, boundary):
        self.id = region_id
        self.set_boundary(boundary)

    def set_boundary(self, boundary):
        self.boundary = np.asarray(
            boundary,
            dtype=np.float64,
        )

        self._next_boundary = np.roll(
            self.boundary,
            -1,
            axis=0,
        )

        self._boundary_cross = np.cross(
            self.boundary,
            self._next_boundary,
        )

        self._boundary_dot = np.einsum(
            'ij,ij->i',
            self.boundary,
            self._next_boundary,
        )

        self.center = normalize(
                self.boundary.mean(axis = 0)
                )
        self._interior_winding = self._winding(self.center)

        self._vertices = None

    @property
    def vertices(self):
        if self._vertices is None:
            self._vertices = self._triangulate()
        return self._vertices

    def _winding(self, p):
        p = np.asarray(
            p,
            dtype=np.float64,
        )

        p /= np.linalg.norm(p)

        ap = self.boundary @ p
        bp = self._next_boundary @ p

        numerator = self._boundary_cross @ p

        denominator = (
            self._boundary_dot
            - ap * bp
        )

        return np.arctan2(
            numerator,
            denominator,
        ).sum()


    def _triangulate(self):
        if len(self.boundary) < 3:
            return np.empty((0, 3), dtype = 'f4')

        center = normalize(self.boundary.mean(axis = 0))

        triangles = []
        for i in range(len(self.boundary)):
            triangles.extend(
                    recursively_subdivide_triangle(
                        center,
                        self.boundary[i],
                        self.boundary[(i + 1) % len(self.boundary)],
                        limit = config.MAX_TRIANGLE_ARC,
                        )
                    )
        return np.asarray(triangles, dtype = 'f4')

    def contains(self, point):
        winding = self._winding(point)

        return (
            abs(winding) > math.pi
            and winding * self._interior_winding > 0
        )
