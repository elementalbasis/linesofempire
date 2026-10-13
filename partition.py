from enum import Enum, auto

from common import xyz_to_lonlat

from shapely import (
    LineString,
    Point,
    box,
    get_parts,
    node,
    polygonize,
    unary_union,
)

class BoundaryKind(Enum):
    VORONOI = auto()
    RIVER = auto()
    ADMIN = auto()
    COAST = auto()


BOUNDARY_WEIGHT = {
    BoundaryKind.VORONOI: 1.0,
    BoundaryKind.RIVER: 2.0,
    BoundaryKind.ADMIN: 2.0,
    BoundaryKind.COAST: 4.0,
}


class Atom:
    def __init__(self, atom_id, geometry):
        self.id = atom_id
        self.geometry = geometry

        # Useful historical/debug metadata only.
        self.source_region_id = None

        self.surface_type = None

        self.region_id = None


class AtomEdge:
    def __init__(self, atom_a, atom_b, geometry, kinds):
        self.atom_a = atom_a
        self.atom_b = atom_b

        # Shared line geometry.
        self.geometry = geometry

        # VORONOI, RIVER, COAST, ...
        self.kinds = kinds


class Component:
    def __init__(self, component_id, atom_ids, region_id=None):
        self.id = component_id
        self.atom_ids = set(atom_ids)

        # Not None only for a genuine rooted Region.
        self.region_id = region_id

        # Chosen during an energy pass.
        self.parent = None

    @property
    def is_root(self):
        return self.region_id is not None

class Partition:
    def __init__(self):
        self.atoms = []
        self.edges = []
        self.components = []

    def clear(self):
        self.atoms = []
        self.edges = []
        self.components = []

    @staticmethod
    def _border_linestring(border):
        coords = [
                xyz_to_lonlat(*vertex) for vertex in border.vertices
                ]
        return LineString(coords)

    def build_from_borders(self, world):
        self.clear()
        lines = [
                self._border_linestring(border)
                for border in world.borders.values()
                ]

        if not lines:
            return

        # Temporary planar frame for lonlat polygonization
        frame = box(-180.0, -90.0, 180.0, 90.0)

        linework = unary_union([*lines, frame.boundary])
        linework = node(linework)
        polygons = polygonize(get_parts(linework))

        for atom_id, polygon in enumerate(get_parts(polygons)):
            self.atoms.append(
                    Atom(atom_id = atom_id, geometry = polygon)
                    )


        for region_id, (lon, lat) in enumerate(world.voronoi.seeds):
            seed = Point(lon, lat)

            containing = [
                atom
                for atom in self.atoms
                if atom.geometry.covers(seed)
            ]

            if len(containing) != 1:
                print(
                    f'WARNING: seed {region_id} is contained by '
                    f'{len(containing)} atoms'
                )
                continue

            containing[0].region_id = region_id

        for atom in self.atoms:
            self.components.append(
                Component(
                    component_id=len(self.components),
                    atom_ids={atom.id},
                    region_id=atom.region_id,
                )
            )

        roots = sum(
            component.is_root
            for component in self.components
        )

        orphans = len(self.components) - roots

        print(
            f'{len(self.atoms)} atoms from {len(world.regions)} regions: '
            f'{roots} roots, {orphans} orphans'
        )
