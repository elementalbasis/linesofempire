import numpy as np
import math

import config
from common import normalize, recursively_subdivide_triangle

class Region:
    def __init__(self, region_id, boundary):
        self.id = region_id
        self.set_boundary(boundary)

    '''
    def set_boundary(self, boundary):
        self.boundary = np.asarray(boundary, dtype = 'f4')
        self.vertices = self._triangulate()
    '''

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

        #self.vertices = self._triangulate()
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

        #vertices = []
        triangles = []
        for i in range(len(self.boundary)):
            #vertices.extend([
            #triangles.append((
            triangles.extend(
                    recursively_subdivide_triangle(
                        center,
                        self.boundary[i],
                        self.boundary[(i + 1) % len(self.boundary)],
                        limit = config.MAX_TRIANGLE_ARC,
                        )
                    )
                #center,
                #self.boundary[i],
                #self.boundary[(i + 1) % len(self.boundary)],
                #])
                #))

        #return np.asarray(vertices, dtype = 'f4')
        return np.asarray(triangles, dtype = 'f4')

    '''
    def contains(self, point, eps = 1e-6):
        point = np.asarray(point, dtype = np.float64)
        triangles = self.vertices.reshape((-1, 3, 3))
        for a, b, c in triangles:
            s1 = np.dot(np.cross(a, b), point)
            s2 = np.dot(np.cross(b, c), point)
            s3 = np.dot(np.cross(c, a), point)

            if (
                    (s1 >= -eps and s2 >= -eps and s3 >= -eps)
                    or
                    (s1 <= eps and s2 <= eps and s3 <= eps)
                    ):
                return True
        return False
    '''

    '''
    def contains(self, point):
        p = np.asarray(point, dtype=np.float64)
        p /= np.linalg.norm(p)

        a = self.boundary.astype(np.float64)
        b = np.roll(a, -1, axis=0)

        # Signed angle subtended by each polygon edge as viewed
        # from the test point on the sphere.
        numerator = np.einsum(
            'ij,j->i',
            np.cross(a, b),
            p,
        )

        denominator = (
            np.einsum('ij,ij->i', a, b)
            - (a @ p) * (b @ p)
        )

        winding = np.sum(
            np.arctan2(
                numerator,
                denominator,
            )
        )

        return abs(winding) > math.pi
    '''

    '''
    def contains(self, point):
        p = np.asarray(
            point,
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

        winding = np.arctan2(
            numerator,
            denominator,
        ).sum()

        return abs(winding) > math.pi
    '''
    def contains(self, point):
        winding = self._winding(point)

        return (
            abs(winding) > math.pi
            and winding * self._interior_winding > 0
        )
