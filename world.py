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
from border import Border, generate_land_border
from partition import Partition

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

        self.land_geometries = land
        self.river_geometries = rivers
        self.coastline_geometries = coastlines
        self.lake_geometries = lakes
        self.admin_border_geometries = admin_borders

        self.voronoi = Voronoi()
        self.borders = {}
        self.regions = []
        self.hovered_region = None

        self.partition = Partition()

        self.cities_df = pd.read_csv(CITIES_FILENAME, sep = '\t')

        self.river_paths = self._line_paths(rivers)
        self.coastline_paths = self._line_paths(coastlines)
        self.admin_border_paths = self._line_paths(admin_borders)

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
        self.borders = {}
        self.partition.clear()
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

    def generate_borders(self):
        self.borders = {}

        for (a, b), region_ids in self.voronoi.edges.items():
            # Every ordinary spherical Voronoi edge should separate two cells.
            if len(region_ids) != 2:
                continue

            region_a, region_b = region_ids

            border = Border(
                region_a=region_a,
                region_b=region_b,
                start=self.voronoi.vertices[a],
                end=self.voronoi.vertices[b],
            )

            generate_land_border(border)

            self.borders[border.key] = border

        self._rebuild_regions_from_borders()
        self.partition.build_from_borders(self)

    @property
    def border_vertices(self):
        vertices = []

        for border in self.borders.values():
            points = border.vertices

            for a, b in zip(
                points[:-1],
                points[1:],
            ):
                vertices.extend((a, b))

        return np.asarray(vertices, dtype='f4')

    def clear_borders(self):
        self.borders = {}
        self.partition.clear()
        self._rebuild_regions_from_voronoi()


    def _rebuild_regions_from_borders(self):
        regions = []

        edge_regions = self.voronoi.edges

        for region_id, indices in enumerate(self.voronoi.region_indices):
            boundary = []

            for a, b in zip(
                indices,
                indices[1:] + indices[:1],
            ):
                edge_key = tuple(sorted((a, b)))
                region_ids = edge_regions[edge_key]

                border_key = tuple(sorted(region_ids))
                border = self.borders[border_key]

                vertices = border.vertices

                # Border orientation may be opposite to this region's
                # traversal around its polygon.
                if not np.allclose(
                    vertices[0],
                    self.voronoi.vertices[a],
                ):
                    vertices = vertices[::-1]

                # Exclude the final endpoint because the following
                # border starts at the same Voronoi vertex.
                boundary.extend(vertices[:-1])

            regions.append(
                Region(
                    region_id,
                    np.asarray(boundary, dtype='f8'),
                )
            )

        self.regions = regions
        self.hovered_region = None

    def reroll_borders(self):
        self.partition.clear()

        for border in self.borders.values():
            generate_land_border(border)

        self._rebuild_regions_from_borders()
        self.partition.build_from_borders(self)

    @property
    def atom_edge_vertices(self):
        vertices = []

        partition = self.partition

        for edge in partition.edges:
            if not partition.edge_separates_atoms(edge):
                continue

            start = partition.vertices[
                edge.vertex_a
            ].point

            end = partition.vertices[
                edge.vertex_b
            ].point

            vertices.extend((
                start,
                end,
            ))

        return np.asarray(
            vertices,
            dtype='f4',
        )

    @staticmethod
    def _line_paths(geometries):
        paths = []

        for geometry in geometries:
            for line in get_parts(geometry):
                points = np.asarray(
                    [
                        lonlat_to_xyz(lon, lat)
                        for lon, lat in line.coords
                    ],
                    dtype='f8',
                )

                if len(points) >= 2:
                    paths.append(points)

        return paths

    @property
    def region_edge_vertices(self):
        vertices = []

        partition = self.partition

        for edge in partition.edges:
            if not partition.edge_separates_regions(edge):
                continue

            start = partition.vertices[
                edge.vertex_a
            ].point

            end = partition.vertices[
                edge.vertex_b
            ].point

            vertices.extend((
                start,
                end,
            ))

        return np.asarray(
            vertices,
            dtype='f4',
        )
