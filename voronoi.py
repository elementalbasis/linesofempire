import numpy as np
from scipy.spatial import SphericalVoronoi

from common import lonlat_to_xyz, xyz_to_lonlat

# Mutable spherical Voronoi generator.
# Seeds are stored as lonlat.
# `vertices` and `region_indices` are derived SciPy topology.
class Voronoi:
    def __init__(self):
        self.seeds = []
        self.vertices = []
        self.region_indices = []

    def rebuild(self):
        if len(self.seeds) < 4:
            self.vertices = np.empty((0,3), dtype = 'f8')
            self.region_indices = []
            return

        points = np.asarray(
                [lonlat_to_xyz(lon, lat) for lon, lat in self.seeds]
                )

        sv = SphericalVoronoi(points)
        sv.sort_vertices_of_regions()

        self.vertices = sv.vertices
        self.region_indices = sv.regions

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
        if not self.region_indices:
            return np.empty((0, 3), dtype = 'f4')

        vertices = []

        for a, b in self.edges:
            vertices.extend((
                self.vertices[a],
                self.vertices[b],
                ))

        return np.asarray(vertices, dtype = 'f4')

    @property
    def edges(self):
        edges = {}

        for region_id, region in enumerate(self.region_indices):
            for a, b in zip(
                region,
                region[1:] + region[:1],
            ):
                edge_key = tuple(sorted((a, b)))

                if edge_key not in edges:
                    edges[edge_key] = []

                edges[edge_key].append(region_id)

        return edges


    def nearest_seed(self, point, max_angle):
        if point is None or not self.seeds:
            return None

        seeds = self.seed_vertices.astype('f8')
        point = np.asarray(point, dtype='f8')

        # Unit vectors: dot product = cosine of angular distance.
        dots = seeds @ point
        index = int(np.argmax(dots))

        if dots[index] >= np.cos(max_angle):
            return index

        return None


    def move_seed(self, index, point):
        lon, lat = xyz_to_lonlat(*point)
        self.seeds[index] = (lon, lat)
        self.rebuild()


    def remove_seed(self, index):
        del self.seeds[index]
        self.rebuild()



    def preview_region(self, index, point):
        if len(self.seeds) < 4:
            return np.empty((0, 3), dtype='f4')

        points = self.seed_vertices.astype('f8').copy()

        point = np.asarray(point, dtype='f8')
        point /= np.linalg.norm(point)
        points[index] = point

        try:
            sv = SphericalVoronoi(points)
            sv.sort_vertices_of_regions()
        except ValueError:
            # Coincident or otherwise degenerate seeds.
            return np.empty((0, 3), dtype='f4')

        return np.asarray(
            sv.vertices[sv.regions[index]],
            dtype='f4',
        )



    def region_at(self, point):
        if point is None or len(self.seeds) < 4:
            return None

        seeds = self.seed_vertices.astype(np.float64)
        point = np.asarray(point, dtype=np.float64)

        return int(np.argmax(seeds @ point))


    def regions_in_rectangle(self, rectangle, camera, width, height):
        if len(self.seeds) < 4:
            return set()

        x1, y1, x2, y2 = rectangle
        east, north, forward = camera.basis()

        seeds = self.seed_vertices.astype(np.float64)

        # Orthographic projection, matching camera.py.
        x = width / 2 + camera.zoom * (seeds @ east)
        y = height / 2 - camera.zoom * (seeds @ north)

        # Exclude seeds on the back of the globe.
        visible = (seeds @ forward) >= 0

        inside = (
            visible
            & (x >= x1)
            & (x <= x2)
            & (y >= y1)
            & (y <= y2)
        )

        return set(np.flatnonzero(inside).tolist())

