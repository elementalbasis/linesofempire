import cartopy.io.shapereader as shpreader
import math
import numpy as np
import pandas as pd

# This is needed to convert QGIS data into a list of points
from shapely import get_parts, constrained_delaunay_triangles



# Import this project's files
import config
from common import lonlat_to_xyz
from voronoi import Voronoi
from region import Region

CITIES_FILENAME = 'misc/cities.tsv'


class World:
    def get_asset(resolution, category, name):
        filename = shpreader.natural_earth(
                resolution = resolution,
                category = category,
                name = name,
                )
        asset = list(
                shpreader.Reader(filename).geometries()
                )
        return asset

    def __init__(self):
        # Get Natural Earth assets
        self.land_asset = World.get_asset(
                config.MAP_SCALE,
                'physical',
                'land',
                )
        self.lakes_asset = World.get_asset(
                config.MAP_SCALE,
                'physical',
                'lakes',
                )
        self.rivers_asset = World.get_asset(
                config.MAP_SCALE,
                'physical',
                'rivers_lake_centerlines',
                )
        self.coastlines_asset = World.get_asset(
                config.MAP_SCALE,
                'physical',
                'coastline',
                )
        self.borders_asset = World.get_asset(
                config.MAP_SCALE,
                'cultural',
                'admin_0_boundary_lines_land',
                )

        self._load_ocean_vertices()
        self._load_land_vertices()
        self._load_rivers_vertices()
        self._load_lakes_vertices()
        self._load_borders_vertices()
        self._load_coastlines_vertices()

        self.voronoi = Voronoi()
        self.regions = []

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

    def _load_coastlines_vertices(self):
        coastlines_vertices = []
        for geom in self.coastlines_asset:
            #for line in line_parts(geom):
            for line in get_parts(geom):
                coords = list(line.coords)
                xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]

                for a, b in zip(xyz[:-1], xyz[1:]):
                    coastlines_vertices.append(a)
                    coastlines_vertices.append(b)
        self.coastlines_vertices = np.asarray(
                coastlines_vertices,
                dtype = 'f4',
                )

    def _load_land_vertices(self):
        # Load land polygons
        land_vertices = []
        for geom in self.land_asset:
            for polygon in get_parts(geom):
                for triangle in get_parts(constrained_delaunay_triangles(polygon)):
                    # These coordinates come in a closed loop, so we must exclude the
                    # last element.
                    coords = list(triangle.exterior.coords)[:-1]

                    for lon, lat in coords:
                        land_vertices.append(
                                lonlat_to_xyz(lon, lat)
                                )
        self.land_vertices = np.asarray(
                land_vertices,
                dtype = 'f4',
                )

    def _load_lakes_vertices(self):
        # Load lake polygons
        lakes_vertices = []
        for geom in self.lakes_asset:
            for polygon in get_parts(geom):
                for triangle in get_parts(constrained_delaunay_triangles(polygon)):
                    coords = list(triangle.exterior.coords)[:-1]

                    for lon, lat in coords:
                        lakes_vertices.append(
                                lonlat_to_xyz(lon, lat)
                                )
        self.lakes_vertices = np.asarray(
                lakes_vertices,
                dtype = 'f4',
                )

    def _load_rivers_vertices(self):
        # Load river lines
        rivers_vertices = []
        for geom in self.rivers_asset:
            for line in get_parts(geom):
                coords = list(line.coords)
                xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]

                for a, b in zip(xyz[:-1], xyz[1:]):
                    rivers_vertices.append(a)
                    rivers_vertices.append(b)

        self.rivers_vertices = np.asarray(
                rivers_vertices,
                dtype = 'f4'
                )

    def _load_borders_vertices(self):
        # Load international borders
        borders_vertices = []
        for geom in self.borders_asset:
            for line in get_parts(geom):
                coords = list(line.coords)
                xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]
                for a, b in zip(xyz[:-1], xyz[1:]):
                    borders_vertices.append(a)
                    borders_vertices.append(b)
        self.borders_vertices = np.asarray(
                borders_vertices,
                dtype = 'f4'
                )

    def _rebuild_regions_from_voronoi(self):
        self.regions = []

        for region_id, indices in enumerate(self.voronoi.region_indices):
            boundary = self.voronoi.vertices[indices]
            self.regions.append(
                    Region(region_id, boundary)
                    )

    def add_voronoi_seed(self, point):
        self.voronoi.add_seed(point)
        self._rebuild_regions_from_voronoi()
