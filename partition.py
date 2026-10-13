from enum import Enum, auto

import numpy as np

from common import angular_distance, normalize
from spherical import (
    arc_intersections,
    outgoing_angle,
    same_point,
    spherical_polygon_area,
    spherical_polygon_contains,
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


class SourceArc:
    def __init__(
        self,
        start,
        end,
        kind,
        source_id=None,
    ):
        self.start = normalize(
            np.asarray(start, dtype=np.float64)
        )

        self.end = normalize(
            np.asarray(end, dtype=np.float64)
        )

        self.kind = kind
        self.source_id = source_id


class Vertex:
    def __init__(self, vertex_id, point):
        self.id = vertex_id

        self.point = normalize(
            np.asarray(point, dtype=np.float64)
        )

        self.outgoing = []


class PartitionEdge:
    def __init__(
        self,
        edge_id,
        vertex_a,
        vertex_b,
        kind,
        source_id=None,
    ):
        self.id = edge_id

        self.vertex_a = vertex_a
        self.vertex_b = vertex_b

        self.kinds = {kind}
        self.source_ids = set()

        if source_id is not None:
            self.source_ids.add(source_id)

        self.halfedges = None
        self.length = None


class HalfEdge:
    def __init__(
        self,
        halfedge_id,
        edge_id,
        origin,
        destination,
    ):
        self.id = halfedge_id
        self.edge_id = edge_id

        self.origin = origin
        self.destination = destination

        self.twin = None
        self.next = None

        # Face on the left side of this directed half-edge.
        self.atom_id = None


class Atom:
    def __init__(
        self,
        atom_id,
        halfedge_ids,
        vertex_ids,
        area,
    ):
        self.id = atom_id

        self.halfedge_ids = tuple(halfedge_ids)
        self.vertex_ids = tuple(vertex_ids)

        self.area = area

        # Root Region if a seed lies inside.
        # None means orphan.
        self.region_id = None

        self.surface_type = None


class Component:
    def __init__(
        self,
        component_id,
        atom_ids,
        region_id=None,
    ):
        self.id = component_id
        self.atom_ids = set(atom_ids)

        self.region_id = region_id
        self.parent = None

    @property
    def is_root(self):
        return self.region_id is not None


class Partition:
    def __init__(self):
        self.vertices = []
        self.edges = []
        self.halfedges = []

        self.atoms = []
        self.components = []

        self._vertex_lookup = {}
        self._edge_lookup = {}

    def clear(self):
        self.vertices = []
        self.edges = []
        self.halfedges = []

        self.atoms = []
        self.components = []

        self._vertex_lookup = {}
        self._edge_lookup = {}

    # ----------------------------------------------------------
    # Source geometry
    # ----------------------------------------------------------

    @staticmethod
    def _border_arcs(world):
        arcs = []

        for border in world.borders.values():
            points = np.asarray(
                border.vertices,
                dtype=np.float64,
            )

            for start, end in zip(
                points[:-1],
                points[1:],
            ):
                if angular_distance(start, end) < 1e-10:
                    continue

                arcs.append(
                    SourceArc(
                        start=start,
                        end=end,
                        kind=BoundaryKind.VORONOI,
                        source_id=border.key,
                    )
                )

        return arcs

    # ----------------------------------------------------------
    # Noding
    # ----------------------------------------------------------

    def _intern_vertex(self, point):
        point = normalize(
            np.asarray(point, dtype=np.float64)
        )

        # First implementation: quantization serves as our snap grid.
        key = tuple(
            np.round(point, decimals=9)
        )

        existing = self._vertex_lookup.get(key)

        if existing is not None:
            return existing

        vertex_id = len(self.vertices)

        self.vertices.append(
            Vertex(
                vertex_id,
                point,
            )
        )

        self._vertex_lookup[key] = vertex_id

        return vertex_id

    def _add_edge(
        self,
        vertex_a,
        vertex_b,
        kind,
        source_id,
    ):
        if vertex_a == vertex_b:
            return

        key = tuple(
            sorted((vertex_a, vertex_b))
        )

        existing = self._edge_lookup.get(key)

        if existing is not None:
            edge = self.edges[existing]
            edge.kinds.add(kind)

            if source_id is not None:
                edge.source_ids.add(source_id)

            return

        edge_id = len(self.edges)

        edge = PartitionEdge(
            edge_id=edge_id,
            vertex_a=vertex_a,
            vertex_b=vertex_b,
            kind=kind,
            source_id=source_id,
        )

        edge.length = angular_distance(
            self.vertices[vertex_a].point,
            self.vertices[vertex_b].point,
        )

        self.edges.append(edge)
        self._edge_lookup[key] = edge_id

    def _node_arcs(self, arcs):
        split_points = [
            [arc.start, arc.end]
            for arc in arcs
        ]

        # First implementation is intentionally O(n²).
        # Optimize only if profiling says we need to.
        for i in range(len(arcs)):
            arc_a = arcs[i]

            for j in range(i + 1, len(arcs)):
                arc_b = arcs[j]

                intersections = arc_intersections(
                    arc_a.start,
                    arc_a.end,
                    arc_b.start,
                    arc_b.end,
                )

                for point in intersections:
                    split_points[i].append(point)
                    split_points[j].append(point)

        for arc, points in zip(
            arcs,
            split_points,
        ):
            points.sort(
                key=lambda point:
                    angular_distance(
                        arc.start,
                        point,
                    )
            )

            unique = []

            for point in points:
                if (
                    not unique
                    or not same_point(
                        point,
                        unique[-1],
                    )
                ):
                    unique.append(point)

            for start, end in zip(
                unique[:-1],
                unique[1:],
            ):
                if angular_distance(start, end) < 1e-10:
                    continue

                vertex_a = self._intern_vertex(start)
                vertex_b = self._intern_vertex(end)

                self._add_edge(
                    vertex_a,
                    vertex_b,
                    arc.kind,
                    arc.source_id,
                )

    # ----------------------------------------------------------
    # Half-edge topology
    # ----------------------------------------------------------

    def _build_halfedges(self):
        self.halfedges = []

        for vertex in self.vertices:
            vertex.outgoing = []

        for edge in self.edges:
            first_id = len(self.halfedges)
            second_id = first_id + 1

            first = HalfEdge(
                halfedge_id=first_id,
                edge_id=edge.id,
                origin=edge.vertex_a,
                destination=edge.vertex_b,
            )

            second = HalfEdge(
                halfedge_id=second_id,
                edge_id=edge.id,
                origin=edge.vertex_b,
                destination=edge.vertex_a,
            )

            first.twin = second_id
            second.twin = first_id

            self.halfedges.extend((
                first,
                second,
            ))

            edge.halfedges = (
                first_id,
                second_id,
            )

            self.vertices[first.origin].outgoing.append(
                first_id
            )

            self.vertices[second.origin].outgoing.append(
                second_id
            )

        # Sort every star of outgoing edges in tangent-plane order.
        for vertex in self.vertices:
            vertex.outgoing.sort(
                key=lambda halfedge_id:
                    outgoing_angle(
                        vertex.point,
                        self.vertices[
                            self.halfedges[
                                halfedge_id
                            ].destination
                        ].point,
                    )
            )

        # With outgoing edges in CCW order, taking the edge
        # immediately clockwise from the twin keeps the face
        # on our left.
        for halfedge in self.halfedges:
            destination = self.vertices[
                halfedge.destination
            ]

            outgoing = destination.outgoing

            twin_index = outgoing.index(
                halfedge.twin
            )

            halfedge.next = outgoing[
                (twin_index - 1) % len(outgoing)
            ]

    # ----------------------------------------------------------
    # Faces / atoms
    # ----------------------------------------------------------

    def _build_atoms(self):
        self.atoms = []

        visited = set()

        for start_id in range(len(self.halfedges)):
            if start_id in visited:
                continue

            path = []
            local = set()

            current_id = start_id

            while current_id not in local:
                local.add(current_id)
                path.append(current_id)

                current_id = self.halfedges[
                    current_id
                ].next

            if current_id != start_id:
                raise RuntimeError(
                    'Half-edge walk entered a cycle '
                    'that did not return to its start.'
                )

            visited.update(path)

            vertex_ids = [
                self.halfedges[
                    halfedge_id
                ].origin
                for halfedge_id in path
            ]

            if len(set(vertex_ids)) < 3:
                continue

            points = [
                self.vertices[
                    vertex_id
                ].point
                for vertex_id in vertex_ids
            ]

            area = spherical_polygon_area(
                points
            )

            if area < 1e-12:
                continue

            atom_id = len(self.atoms)

            atom = Atom(
                atom_id=atom_id,
                halfedge_ids=path,
                vertex_ids=vertex_ids,
                area=area,
            )

            self.atoms.append(atom)

            for halfedge_id in path:
                self.halfedges[
                    halfedge_id
                ].atom_id = atom_id

    def _assign_roots(self, world):
        for region_id, seed in enumerate(
            world.voronoi.seed_vertices
        ):
            seed = np.asarray(
                seed,
                dtype=np.float64,
            )

            containing = []

            for atom in self.atoms:
                points = [
                    self.vertices[
                        vertex_id
                    ].point
                    for vertex_id
                    in atom.vertex_ids
                ]

                if spherical_polygon_contains(
                    points,
                    seed,
                ):
                    containing.append(atom)

            if len(containing) != 1:
                print(
                    f'WARNING: seed {region_id} '
                    f'is contained by '
                    f'{len(containing)} atoms'
                )

                continue

            containing[0].region_id = region_id

    def _build_components(self):
        self.components = []

        for atom in self.atoms:
            self.components.append(
                Component(
                    component_id=len(
                        self.components
                    ),
                    atom_ids={atom.id},
                    region_id=atom.region_id,
                )
            )

    # ----------------------------------------------------------
    # Public construction
    # ----------------------------------------------------------

    def build_from_borders(self, world):
        self.clear()

        arcs = self._border_arcs(world)

        if not arcs:
            return

        self._node_arcs(arcs)
        self._build_halfedges()
        self._build_atoms()
        self._assign_roots(world)
        self._build_components()

        roots = sum(
            component.is_root
            for component
            in self.components
        )

        orphans = (
            len(self.components)
            - roots
        )

        print(
            f'{len(self.vertices)} vertices, '
            f'{len(self.edges)} edges, '
            f'{len(self.atoms)} atoms: '
            f'{roots} roots, '
            f'{orphans} orphans'
        )
