import cartopy.io.shapereader as shpreader
import math
import numpy as np
import pandas as pd

# Shapely helpers for decomposing and triangulating Natural Earth geometry
from shapely import get_parts, constrained_delaunay_triangles



# Import this project's files
import config
from common import lonlat_to_xyz
from voronoi import Voronoi
from region import Region

CITIES_FILENAME = 'misc/cities.tsv'


class World:
    def __init__(self):
        # Get Natural Earth assets
        land = World._load_natural_earth(
                config.MAP_SCALE,
                'physical',
                'land',
                )
        lakes = World._load_natural_earth(
                config.MAP_SCALE,
                'physical',
                'lakes',
                )
        rivers = World._load_natural_earth(
                config.MAP_SCALE,
                'physical',
                'rivers_lake_centerlines',
                )
        coastlines = World._load_natural_earth(
                config.MAP_SCALE,
                'physical',
                'coastline',
                )
        admin_borders = World._load_natural_earth(
                config.MAP_SCALE,
                'cultural',
                'admin_0_boundary_lines_land',
                )

        self._load_ocean_vertices()
        self.land_vertices = self._polygon_vertices(land)
        self.lakes_vertices = self._polygon_vertices(lakes)
        self.rivers_vertices = self._line_vertices(rivers)
        self.coastlines_vertices = self._line_vertices(coastlines)
        self.admin_borders_vertices = self._line_vertices(admin_borders)

        self.voronoi = Voronoi()
        self.regions = []
        self.hovered_region = None

        self.cities_df = pd.read_csv(CITIES_FILENAME, sep = '\t')

    # Create ocean disk out of triangles
    def _load_ocean_vertices(self):
        ocean_vertices = [(0.0, 0.0)] # Start with the origin
        for i in range(config.OCEAN_SEGMENTS + 1):
            angle = 2 * math.pi * i / config.OCEAN_SEGMENTS
            ocean_vertices.append((math.cos(angle), math.sin(angle)))
        self.ocean_vertices = np.asarray(
                ocean_vertices,
                dtype = 'f4'
                )

    def _rebuild_regions_from_voronoi(self):
        self.regions = []

        for region_id, indices in enumerate(self.voronoi.region_indices):
            boundary = self.voronoi.vertices[indices]
            self.regions.append(
                    Region(region_id, boundary)
                    )

        self.hovered_region = None

    def add_voronoi_seed(self, point):
        self.voronoi.add_seed(point)
        self._rebuild_regions_from_voronoi()

    def region_at(self, point):
        if point is None:
            return None

        for region in self.regions:
            if region.contains(point):
                return region

        return None

    @staticmethod
    def _line_vertices(geometries):
        vertices = []

        for geometry in geometries:
            for line in get_parts(geometry):
                points = [
                    lonlat_to_xyz(lon, lat)
                    for lon, lat in line.coords
                ]

                for a, b in zip(points[:-1], points[1:]):
                    vertices.extend((a, b))

        return np.asarray(vertices, dtype='f4')


    @staticmethod
    def _polygon_vertices(geometries):
        vertices = []

        for geometry in geometries:
            for polygon in get_parts(geometry):
                triangles = constrained_delaunay_triangles(polygon)

                for triangle in get_parts(triangles):
                    # Shapely exterior rings repeat the first coordinate.
                    for lon, lat in list(triangle.exterior.coords)[:-1]:
                        vertices.append(lonlat_to_xyz(lon, lat))

        return np.asarray(vertices, dtype='f4')

    @staticmethod
    def _load_natural_earth(resolution, category, name):
        filename = shpreader.natural_earth(
                resolution = resolution,
                category = category,
                name = name,
                )
        asset = list(
                shpreader.Reader(filename).geometries()
                )
        return asset

