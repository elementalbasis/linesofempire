import numpy as np

import config
from common import normalize, recursively_subdivide_triangle

class Region:
    def __init__(self, region_id, boundary):
        self.id = region_id
        self.set_boundary(boundary)

    def set_boundary(self, boundary):
        self.boundary = np.asarray(boundary, dtype = 'f4')
        self.vertices = self._triangulate()


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
                        limit = config.MAX_VECTOR_ARC,
                        )
                    )
                #center,
                #self.boundary[i],
                #self.boundary[(i + 1) % len(self.boundary)],
                #])
                #))

        #return np.asarray(vertices, dtype = 'f4')
        return np.asarray(triangles, dtype = 'f4')

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
