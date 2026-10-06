import numpy as np
from scipy.spatial import SphericalVoronoi

from common import lonlat_to_xyz, xyz_to_lonlat

class Voronoi:
    def __init__(self):
        self.seeds = []
        self.vertices = []
        self.regions = []

    def rebuild(self):
        if len(self.seeds) < 4:
            return

        points = np.asarray(list(set(
            lonlat_to_xyz(lon, lat) for lon, lat in self.seeds
            )))

        print(points)
        sv = SphericalVoronoi(points)
        sv.sort_vertices_of_regions()

        self.vertices = sv.vertices
        self.regions = sv.regions

    def add_seed(self, point):
        lon, lat = xyz_to_lonlat(*point)
        self.seeds.append((lon, lat))
        self.rebuild()

    @property
    def seed_vertices(self):
        return np.asarray(
                [lonlat_to_xyz(lon, lat) for lon, lat in self.seeds],
                dtype = 'f4',
                )

    @property
    def edge_vertices(self):
        if not self.regions:
            return np.empty((0, 3), dtype = 'f4')

        seen = set()
        vertices = []

        for region in self.regions:
            for a, b in zip(
                    region,
                    region[1:] + region[:1],
                    ):
                edge = tuple(sorted((a, b)))

                if edge in seen:
                    continue

                seen.add(edge)

                vertices.append(self.vertices[a])
                vertices.append(self.vertices[b])

        return np.asarray(vertices, dtype = 'f4')
