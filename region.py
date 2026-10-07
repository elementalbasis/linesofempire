import numpy as np

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

        center = self.boundary.mean(axis = 0)
        center /= np.linalg.norm(center)

        vertices = []
        for i in range(len(self.boundary)):
            vertices.extend([
                center,
                self.boundary[i],
                self.boundary[(i + 1) % len(self.boundary)],
                ])

        return np.asarray(vertices, dtype = 'f4')
