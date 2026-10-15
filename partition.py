import math
import numpy as np
from enum import Enum, auto
from scipy.spatial import cKDTree, ConvexHull, QhullError

from shapely import contains_xy, union_all

from common import angular_distance, normalize
from spherical import (
    arc_intersections,
    outgoing_angle,
    same_point,
    spherical_polygon_area,
    spherical_polygon_contains,
    closest_point_on_arc,
    closest_points_between_arcs,
)


class BoundaryKind(Enum):
    VORONOI = auto()
    RIVER = auto()
    ADMIN = auto()
    COAST = auto()
    SNAP = auto()


class SurfaceType(Enum):
    LAND = auto()
    SEA = auto()


BOUNDARY_WEIGHT = {
    BoundaryKind.VORONOI: 1.0,
    BoundaryKind.RIVER: 2.0,
    BoundaryKind.ADMIN: 2.0,
    BoundaryKind.COAST: 4.0,
    BoundaryKind.SNAP: 0.0,
}

LAMBDA_CONTACT = 1.0
LAMBDA_REOCK = 1.0
LAMBDA_TYPE = 1.0
LAMBDA_BOUNDARY = 1.0

class SourcePath:
    def __init__(
        self,
        points,
        kind,
        source_id=None,
        closed=False,
    ):
        self.points = np.asarray(
            points,
            dtype=np.float64,
        )

        self.kind = kind
        self.source_id = source_id
        self.closed = closed

        pairs = list(zip(
            self.points[:-1],
            self.points[1:],
        ))

        if self.closed:
            pairs.append((
                self.points[-1],
                self.points[0],
            ))

        self._arcs = [
            SourceArc(
                start=start,
                end=end,
                kind=self.kind,
                source_id=self.source_id,
            )
            for start, end in pairs
            if angular_distance(
                start,
                end,
            ) >= 1e-10
        ]

    @property
    def arcs(self):
        return self._arcs

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

        self.terminal_start = False
        self.terminal_end = False

        self._refresh()

    def _refresh(self):
        self.length = angular_distance(
            self.start,
            self.end,
        )

        self.midpoint = normalize(
            self.start + self.end
        )

        self.radius = 0.5 * self.length

    def set_start(self, point):
        self.start = normalize(
            np.asarray(point, dtype=np.float64)
        )
        self._refresh()

    def set_end(self, point):
        self.end = normalize(
            np.asarray(point, dtype=np.float64)
        )
        self._refresh()


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

        self.active = True

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

        self.region_surface_types = {}
        self.orphan_ids = set()
        self._land_domain = None

        self._vertex_lookup = {}
        self._edge_lookup = {}

    def clear(self):
        self.vertices = []
        self.edges = []
        self.halfedges = []

        self.atoms = []
        self.components = []

        self.region_surface_types = {}
        self.orphan_ids = set()

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

    def _node_arcs(
        self,
        arcs,
        snap_tolerance=math.radians(0.05),
    ):
        split_points = [
            [arc.start, arc.end]
            for arc in arcs
        ]

        connectors = []
        connector_keys = set()

        for i, j in self._candidate_arc_pairs(
            arcs,
            padding=snap_tolerance,
        ):
            arc_a = arcs[i]
            arc_b = arcs[j]

            # Segments belonging to the same source path already
            # know their own connectivity.
            if (
                arc_a.kind == arc_b.kind
                and arc_a.source_id == arc_b.source_id
            ):
                continue

            maximum_separation = min(
                math.pi,
                arc_a.radius
                + arc_b.radius
                + snap_tolerance,
            )

            if (
                np.dot(
                    arc_a.midpoint,
                    arc_b.midpoint,
                )
                < math.cos(maximum_separation)
            ):
                continue

            intersections = arc_intersections(
                arc_a.start,
                arc_a.end,
                arc_b.start,
                arc_b.end,
            )

            if intersections:
                for point in intersections:
                    split_points[i].append(point)
                    split_points[j].append(point)

                continue

            # Generated strategic borders must not snap to each other.
            if (
                arc_a.kind == BoundaryKind.VORONOI
                and arc_b.kind == BoundaryKind.VORONOI
            ):
                continue

            point_a, point_b = self._closest_arc_points(arc_a, arc_b)

            # Avoid gluing nearby parallel rivers to rivers,
            # coastlines to coastlines, etc.
            if arc_a.kind == arc_b.kind:
                # Segments of the exact same source path already know
                # how they connect.
                if arc_a.source_id == arc_b.source_id:
                    continue

                # Different source paths of the same feature type may
                # actually be fragments of one real feature. Only allow
                # snapping when at least one side is a true path terminus.
                if not (
                    arc_a.terminal_start
                    or arc_a.terminal_end
                    or arc_b.terminal_start
                    or arc_b.terminal_end
                ):
                    continue

            distance = angular_distance(
                point_a,
                point_b,
            )

            if (
                distance <= 1e-6
                or distance > snap_tolerance
            ):
                continue

            split_points[i].append(point_a)
            split_points[j].append(point_b)

            key = tuple(sorted((
                tuple(np.round(point_a, 9)),
                tuple(np.round(point_b, 9)),
            )))

            if key not in connector_keys:
                connector_keys.add(key)
                connectors.append((
                    point_a,
                    point_b,
                ))

        # Existing split/sort/add-edge portion.
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

        # Tiny topological bridges are already noded because their
        # endpoints were inserted into the corresponding source arcs.
        for snap_id, (start, end) in enumerate(connectors):
            vertex_a = self._intern_vertex(start)
            vertex_b = self._intern_vertex(end)

            self._add_edge(
                vertex_a,
                vertex_b,
                BoundaryKind.SNAP,
                ('snap', snap_id),
            )

        self.snap_count = len(connectors)

    # ----------------------------------------------------------
    # Half-edge topology
    # ----------------------------------------------------------

    def _build_halfedges(self):
        self.halfedges = []

        for vertex in self.vertices:
            vertex.outgoing = []

        for edge in self.edges:
            edge.halfedges = None
            if not edge.active:
                continue

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

    def _atom_probe_point(self, atom):
        halfedge = self.halfedges[
            atom.halfedge_ids[0]
        ]

        start = self.vertices[
            halfedge.origin
        ].point

        end = self.vertices[
            halfedge.destination
        ].point

        midpoint = normalize(
            start + end
        )

        # The face walker keeps the atom on the left side of each
        # directed half-edge.  The great-circle normal therefore
        # points from the boundary into the atom.
        left = np.cross(
            start,
            end,
        )

        left_length = np.linalg.norm(left)

        if left_length < 1e-12:
            return midpoint

        left /= left_length

        edge_length = angular_distance(
            start,
            end,
        )

        epsilon = min(
            1e-5,
            0.1 * edge_length,
        )

        return normalize(
            midpoint
            + math.tan(epsilon) * left
        )

    def _land_mask(self, world, points):
        points = np.asarray(
            points,
            dtype=np.float64,
        )

        if not len(points):
            return np.empty(
                0,
                dtype=bool,
            )

        if self._land_domain is None:
            self._land_domain = union_all(
                world.land_geometries
            )

        lon = np.degrees(
            np.arctan2(
                points[:, 1],
                points[:, 0],
            )
        )

        lat = np.degrees(
            np.arcsin(
                np.clip(
                    points[:, 2],
                    -1.0,
                    1.0,
                )
            )
        )

        return np.asarray(
            contains_xy(
                self._land_domain,
                lon,
                lat,
            ),
            dtype=bool,
        )

    def _assign_surface_types(self, world):
        atom_probes = np.asarray(
            [
                self._atom_probe_point(atom)
                for atom in self.atoms
            ],
            dtype=np.float64,
        )

        atom_is_land = self._land_mask(
            world,
            atom_probes,
        )

        for atom, is_land in zip(
            self.atoms,
            atom_is_land,
        ):
            atom.surface_type = (
                SurfaceType.LAND
                if is_land
                else SurfaceType.SEA
            )

        seed_vertices = np.asarray(
            world.voronoi.seed_vertices,
            dtype=np.float64,
        )

        seed_is_land = self._land_mask(
            world,
            seed_vertices,
        )

        self.region_surface_types = {
            region_id: (
                SurfaceType.LAND
                if is_land
                else SurfaceType.SEA
            )
            for region_id, is_land
            in enumerate(seed_is_land)
        }

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

    def _build_arrangement(self, arcs):
        self._node_arcs(arcs)
        self._prune_irrelevant_feature_components()
        self._build_halfedges()
        self._build_atoms()

    def build_from_borders(self, world):
        """Cut the source geometry into atoms and identify seeded roots.

        No automatic orphan assignment occurs during this operation.
        """
        self.clear()

        border_arcs = self._border_arcs(world)

        if not border_arcs:
            return

        river_arcs = self._feature_arcs(
            world.river_paths,
            BoundaryKind.RIVER,
        )

        admin_arcs = self._feature_arcs(
            world.admin_border_paths,
            BoundaryKind.ADMIN,
        )

        coast_arcs = self._feature_arcs(
            world.coastline_paths,
            BoundaryKind.COAST,
        )

        feature_arcs = river_arcs + admin_arcs + coast_arcs
        arcs = border_arcs + feature_arcs


        print(
            f'source arcs: '
            f'{len(border_arcs)} strategic, '
            f'{len(river_arcs)} river, '
            f'{len(admin_arcs)} admin, '
            f'{len(coast_arcs)} coast, '
        )

        self._build_arrangement(arcs)
        self._assign_surface_types(world)
        self._assign_roots(world)
        self._build_components()
        self.orphan_ids = {
            atom.id for atom in self.atoms if atom.region_id is None
        }

        '''
        roots = sum(
            component.is_root
            for component
            in self.components
        )

        orphans = (
            len(self.components)
            - roots
        )


        active_edges = [edge for edge in self.edges if edge.active]
        active_vertices = {vertex_id for edge in active_edges
                           for vertex_id in (edge.vertex_a, edge.vertex_b)}
        euler = len(active_vertices) - len(active_edges) + len(self.atoms)
        print(
            f'{len(self.vertices)} vertices, '
            f'{len(self.edges)} edges, '
            f'{len(self.atoms)} atoms: '
            f'{roots} roots, '
            f'{orphans} orphans'
            f'Euler = {euler}'
        )
        '''


    @staticmethod
    def _feature_arcs(paths, kind):
        arcs = []

        for path_id, points in enumerate(paths):
            path = SourcePath(
                points=points,
                kind=kind,
                source_id=(kind, path_id),
            )

            path_arcs = path.arcs

            if not path_arcs:
                continue

            closed = same_point(
                points[0],
                points[-1],
            )

            if not closed:
                path_arcs[0].terminal_start = True
                path_arcs[-1].terminal_end = True

            arcs.extend(path_arcs)

        return arcs

    def edge_separates_atoms(self, edge):
        if (
            not edge.active
            or edge.halfedges is None
        ):
            return False

        first_id, second_id = edge.halfedges

        first_atom = self.halfedges[
            first_id
        ].atom_id

        second_atom = self.halfedges[
            second_id
        ].atom_id

        return (
            first_atom is not None
            and second_atom is not None
            and first_atom != second_atom
        )


    def _prune_irrelevant_feature_components(self):
        strategic_vertices = set()

        for edge in self.edges:
            if BoundaryKind.VORONOI in edge.kinds:
                strategic_vertices.add(edge.vertex_a)
                strategic_vertices.add(edge.vertex_b)

        # Feature-edge adjacency by vertex.
        adjacency = {}

        feature_edge_ids = []

        for edge in self.edges:
            is_feature = any(
                kind != BoundaryKind.VORONOI
                for kind in edge.kinds
            )

            if not is_feature:
                continue

            feature_edge_ids.append(edge.id)

            adjacency.setdefault(
                edge.vertex_a,
                [],
            ).append(edge.id)

            adjacency.setdefault(
                edge.vertex_b,
                [],
            ).append(edge.id)

        visited = set()

        for start_edge_id in feature_edge_ids:
            if start_edge_id in visited:
                continue

            component_edges = set()
            component_vertices = set()

            stack = [start_edge_id]

            while stack:
                edge_id = stack.pop()

                if edge_id in visited:
                    continue

                visited.add(edge_id)
                component_edges.add(edge_id)

                edge = self.edges[edge_id]

                for vertex_id in (
                    edge.vertex_a,
                    edge.vertex_b,
                ):
                    component_vertices.add(
                        vertex_id
                    )

                    for neighbor_id in adjacency.get(
                        vertex_id,
                        (),
                    ):
                        if neighbor_id not in visited:
                            stack.append(neighbor_id)

            contacts = (
                component_vertices
                & strategic_vertices
            )

            # A feature network with fewer than two strategic
            # contacts cannot cut the strategic partition.
            if len(contacts) >= 2:
                continue

            for edge_id in component_edges:
                edge = self.edges[edge_id]

                # Never deactivate the strategic boundary itself,
                # even if a feature happens to coincide with it.
                if BoundaryKind.VORONOI not in edge.kinds:
                    edge.active = False

    @staticmethod
    def _strategic_snap_connectors(
        feature_arcs,
        border_arcs,
        tolerance=math.radians(0.05),
    ):
        if not feature_arcs or not border_arcs:
            return []

        centers = np.asarray(
            [
                arc.midpoint
                for arc in border_arcs
            ],
            dtype=np.float64,
        )

        tree = cKDTree(centers)

        max_border_radius = max(
            arc.radius
            for arc in border_arcs
        )

        connectors = []
        seen = set()

        for feature in feature_arcs:
            search_angle = min(
                math.pi,
                feature.radius
                + max_border_radius
                + tolerance,
            )

            search_chord = (
                2.0
                * math.sin(
                    search_angle / 2.0
                )
            )

            candidates = tree.query_ball_point(
                feature.midpoint,
                search_chord,
            )

            for border_index in candidates:
                border = border_arcs[
                    border_index
                ]

                # If they genuinely intersect, normal
                # noding already handles it.
                if arc_intersections(
                    feature.start,
                    feature.end,
                    border.start,
                    border.end,
                ):
                    continue

                feature_point, border_point = (
                    closest_points_between_arcs(
                        feature.start,
                        feature.end,
                        border.start,
                        border.end,
                    )
                )

                distance = angular_distance(
                    feature_point,
                    border_point,
                )

                if distance > tolerance:
                    continue

                if distance < 1e-10:
                    continue

                key = (
                    tuple(np.round(
                        feature_point,
                        decimals=9,
                    )),
                    tuple(np.round(
                        border_point,
                        decimals=9,
                    )),
                )

                if key in seen:
                    continue

                seen.add(key)

                connectors.append(
                    SourceArc(
                        start=feature_point,
                        end=border_point,
                        kind=BoundaryKind.SNAP,
                        source_id=(
                            'strategic-snap',
                            len(connectors),
                        ),
                    )
                )

        return connectors

    @staticmethod
    def _arc_buckets(
        arcs,
        base_radius=math.radians(0.05),
    ):
        groups = {}

        for index, arc in enumerate(arcs):
            radius = max(arc.radius, 1e-12)

            level = max(
                0,
                math.ceil(
                    math.log2(radius / base_radius)
                ),
            )

            groups.setdefault(level, []).append(index)

        buckets = []

        for indices in groups.values():
            indices = np.asarray(
                indices,
                dtype=np.int64,
            )

            centers = np.asarray(
                [
                    arcs[index].midpoint
                    for index in indices
                ],
                dtype=np.float64,
            )

            buckets.append((
                indices,
                cKDTree(centers),
                max(
                    arcs[index].radius
                    for index in indices
                ),
            ))

        return buckets

    @staticmethod
    def _candidate_arc_pairs(
        arcs,
        padding=0.0,
    ):
        buckets = Partition._arc_buckets(arcs)

        for bucket_a_index, (
            indices_a,
            tree_a,
            radius_a,
        ) in enumerate(buckets):

            for bucket_b_index in range(
                bucket_a_index,
                len(buckets),
            ):
                (
                    indices_b,
                    tree_b,
                    radius_b,
                ) = buckets[bucket_b_index]

                search_angle = min(
                    math.pi,
                    radius_a
                    + radius_b
                    + padding,
                )

                search_chord = (
                    2.0
                    * math.sin(
                        search_angle / 2.0
                    )
                )

                if bucket_a_index == bucket_b_index:
                    pairs = tree_a.query_pairs(
                        search_chord,
                        output_type='ndarray',
                    )

                    for local_a, local_b in pairs:
                        yield (
                            int(indices_a[local_a]),
                            int(indices_a[local_b]),
                        )

                else:
                    neighborhoods = tree_a.query_ball_tree(
                        tree_b,
                        search_chord,
                    )

                    for local_a, local_bs in enumerate(
                        neighborhoods
                    ):
                        a = int(indices_a[local_a])

                        for local_b in local_bs:
                            yield (
                                a,
                                int(indices_b[local_b]),
                            )

    @staticmethod
    def _closest_arc_points(arc_a, arc_b):
        candidates = [
            (
                arc_a.start,
                closest_point_on_arc(
                    arc_a.start,
                    arc_b.start,
                    arc_b.end,
                ),
            ),
            (
                arc_a.end,
                closest_point_on_arc(
                    arc_a.end,
                    arc_b.start,
                    arc_b.end,
                ),
            ),
            (
                closest_point_on_arc(
                    arc_b.start,
                    arc_a.start,
                    arc_a.end,
                ),
                arc_b.start,
            ),
            (
                closest_point_on_arc(
                    arc_b.end,
                    arc_a.start,
                    arc_a.end,
                ),
                arc_b.end,
            ),
        ]

        return min(
            candidates,
            key=lambda pair:
                angular_distance(
                    pair[0],
                    pair[1],
                ),
        )

    @staticmethod
    def _point_is_terminal(arc, point):
        return (
            (
                arc.terminal_start
                and same_point(point, arc.start)
            )
            or
            (
                arc.terminal_end
                and same_point(point, arc.end)
            )
        )


    @staticmethod
    def _closest_point_on_triangle_to_origin(
        a,
        b,
        c,
    ):
        # Ericson-style closest-point test, specialized to the origin.
        ab = b - a
        ac = c - a
        ap = -a

        d1 = np.dot(ab, ap)
        d2 = np.dot(ac, ap)

        if d1 <= 0.0 and d2 <= 0.0:
            return a

        bp = -b
        d3 = np.dot(ab, bp)
        d4 = np.dot(ac, bp)

        if d3 >= 0.0 and d4 <= d3:
            return b

        vc = d1 * d4 - d3 * d2

        if (
            vc <= 0.0
            and d1 >= 0.0
            and d3 <= 0.0
        ):
            v = d1 / (d1 - d3)
            return a + v * ab

        cp = -c
        d5 = np.dot(ab, cp)
        d6 = np.dot(ac, cp)

        if d6 >= 0.0 and d5 <= d6:
            return c

        vb = d5 * d2 - d1 * d6

        if (
            vb <= 0.0
            and d2 >= 0.0
            and d6 <= 0.0
        ):
            w = d2 / (d2 - d6)
            return a + w * ac

        va = d3 * d6 - d5 * d4

        if (
            va <= 0.0
            and d4 - d3 >= 0.0
            and d5 - d6 >= 0.0
        ):
            w = (
                (d4 - d3)
                / (
                    (d4 - d3)
                    + (d5 - d6)
                )
            )

            return b + w * (c - b)

        denominator = 1.0 / (
            va + vb + vc
        )

        v = vb * denominator
        w = vc * denominator

        return (
            a
            + v * ab
            + w * ac
        )

    @staticmethod
    def _fallback_cap_area(points):
        center = points.mean(axis=0)
        center_length = np.linalg.norm(center)

        if center_length < 1e-12:
            center = points[0]
        else:
            center /= center_length

        cosine_radius = float(
            np.min(points @ center)
        )

        cosine_radius = np.clip(
            cosine_radius,
            -1.0,
            1.0,
        )

        return (
            2.0
            * math.pi
            * (1.0 - cosine_radius)
        )

    @classmethod
    def _minimum_enclosing_cap_area(
        cls,
        points,
    ):
        points = np.asarray(
            points,
            dtype=np.float64,
        )

        if not len(points):
            return 0.0

        points = np.unique(
            np.round(
                points,
                decimals=12,
            ),
            axis=0,
        )

        lengths = np.linalg.norm(
            points,
            axis=1,
            keepdims=True,
        )

        points = points / lengths
        count = len(points)

        if count == 1:
            return 0.0

        if count == 2:
            closest = 0.5 * (
                points[0]
                + points[1]
            )

            cosine_radius = np.clip(
                np.linalg.norm(closest),
                0.0,
                1.0,
            )

            return (
                2.0
                * math.pi
                * (1.0 - cosine_radius)
            )

        if count == 3:
            closest = (
                cls._closest_point_on_triangle_to_origin(
                    points[0],
                    points[1],
                    points[2],
                )
            )

            cosine_radius = np.clip(
                np.linalg.norm(closest),
                0.0,
                1.0,
            )

            return (
                2.0
                * math.pi
                * (1.0 - cosine_radius)
            )

        try:
            hull = ConvexHull(points)
        except QhullError:
            return cls._fallback_cap_area(
                points
            )

        # For the strategic regions we expect the point set to fit in
        # a hemisphere.  If the origin lies in the Euclidean hull, use
        # a conservative valid cap rather than forcing that assumption.
        if np.all(
            hull.equations[:, 3] <= 1e-12
        ):
            return cls._fallback_cap_area(
                points
            )

        minimum_squared = math.inf

        for simplex in hull.simplices:
            a, b, c = points[simplex]

            closest = (
                cls._closest_point_on_triangle_to_origin(
                    a,
                    b,
                    c,
                )
            )

            squared = float(
                np.dot(closest, closest)
            )

            minimum_squared = min(
                minimum_squared,
                squared,
            )

        cosine_radius = math.sqrt(
            max(
                0.0,
                min(
                    1.0,
                    minimum_squared,
                ),
            )
        )

        return (
            2.0
            * math.pi
            * (1.0 - cosine_radius)
        )

    def _reock_score(
        self,
        area,
        vertex_ids,
    ):
        if not vertex_ids:
            return 1.0

        points = np.asarray(
            [
                self.vertices[
                    vertex_id
                ].point
                for vertex_id in vertex_ids
            ],
            dtype=np.float64,
        )

        cap_area = (
            self._minimum_enclosing_cap_area(
                points
            )
        )

        if cap_area <= 1e-12:
            return 1.0

        return float(
            np.clip(
                area / cap_area,
                0.0,
                1.0,
            )
        )

    def _component_metrics(self):
        atom_to_component = {}
        areas = {}
        land_areas = {}
        perimeters = {}
        adjacency = {}
        boundary_vertices = {}

        for component in self.components:
            component_id = component.id

            areas[component_id] = 0.0
            land_areas[component_id] = 0.0
            perimeters[component_id] = 0.0
            adjacency[component_id] = {}
            boundary_vertices[component_id] = set()

            for atom_id in component.atom_ids:
                atom = self.atoms[
                    atom_id
                ]

                atom_to_component[
                    atom_id
                ] = component_id

                areas[
                    component_id
                ] += atom.area

                if (
                    atom.surface_type
                    == SurfaceType.LAND
                ):
                    land_areas[
                        component_id
                    ] += atom.area

        for edge in self.edges:
            if (
                not edge.active
                or edge.halfedges is None
            ):
                continue

            first_id, second_id = (
                edge.halfedges
            )

            atom_a = self.halfedges[
                first_id
            ].atom_id

            atom_b = self.halfedges[
                second_id
            ].atom_id

            component_a = (
                atom_to_component.get(
                    atom_a
                )
                if atom_a is not None
                else None
            )

            component_b = (
                atom_to_component.get(
                    atom_b
                )
                if atom_b is not None
                else None
            )

            # Internal edge of one component.
            if (
                component_a is not None
                and component_a == component_b
            ):
                continue

            edge_vertices = (
                edge.vertex_a,
                edge.vertex_b,
            )

            if component_a is not None:
                perimeters[
                    component_a
                ] += edge.length

                boundary_vertices[
                    component_a
                ].update(edge_vertices)

            if component_b is not None:
                perimeters[
                    component_b
                ] += edge.length

                boundary_vertices[
                    component_b
                ].update(edge_vertices)

            if (
                component_a is None
                or component_b is None
            ):
                continue

            boundary_weight = max(
                BOUNDARY_WEIGHT[kind]
                for kind in edge.kinds
            )

            for source, target in (
                (component_a, component_b),
                (component_b, component_a),
            ):
                contact = adjacency[
                    source
                ].setdefault(
                    target,
                    {
                        'length': 0.0,
                        'weighted_length': 0.0,
                    },
                )

                contact[
                    'length'
                ] += edge.length

                contact[
                    'weighted_length'
                ] += (
                    boundary_weight
                    * edge.length
                )

        surface_types = {}
        reock_scores = {}

        for component in self.components:
            component_id = component.id

            if component.is_root:
                surface_types[
                    component_id
                ] = self.region_surface_types[
                    component.region_id
                ]

            else:
                land_area = land_areas[
                    component_id
                ]

                sea_area = (
                    areas[component_id]
                    - land_area
                )

                surface_types[
                    component_id
                ] = (
                    SurfaceType.LAND
                    if land_area >= sea_area
                    else SurfaceType.SEA
                )

            reock_scores[
                component_id
            ] = self._reock_score(
                areas[component_id],
                boundary_vertices[
                    component_id
                ],
            )

        return (
            areas,
            perimeters,
            adjacency,
            boundary_vertices,
            reock_scores,
            surface_types,
        )

    def _energy(
        self,
        orphan_id,
        candidate_id,
        areas,
        perimeters,
        adjacency,
        boundary_vertices,
        reock_scores,
        surface_types,
        reock_union_cache,
    ):
        contact = adjacency[
            orphan_id
        ][candidate_id]

        perimeter = max(
            perimeters[orphan_id],
            1e-12,
        )

        contact_energy = (
            -LAMBDA_CONTACT
            * contact['length']
            / perimeter
        )

        boundary_energy = (
            LAMBDA_BOUNDARY
            * contact['weighted_length']
            / perimeter
        )

        combined_area = (
            areas[orphan_id]
            + areas[candidate_id]
        )

        pair = tuple(sorted((
            orphan_id,
            candidate_id,
        )))

        if pair not in reock_union_cache:
            combined_vertices = (
                boundary_vertices[
                    orphan_id
                ]
                | boundary_vertices[
                    candidate_id
                ]
            )

            reock_union_cache[
                pair
            ] = self._reock_score(
                combined_area,
                combined_vertices,
            )

        combined_reock = max(
            reock_union_cache[pair],
            1e-12,
        )

        reock_energy = (
            LAMBDA_REOCK
            * reock_scores[
                candidate_id
            ]
            / combined_reock
        )

        sign = (
            1.0
            if (
                surface_types[orphan_id]
                == surface_types[candidate_id]
            )
            else -1.0
        )

        type_energy = (
            -LAMBDA_TYPE
            * areas[orphan_id]
            / combined_area
            * sign
        )

        return (
            contact_energy
            + reock_energy
            + type_energy
            + boundary_energy
        )

    def _choose_parents(self):
        (
            areas,
            perimeters,
            adjacency,
            boundary_vertices,
            reock_scores,
            surface_types,
        ) = self._component_metrics()

        reock_union_cache = {}

        for component in self.components:
            component.parent = None

        for component in self.components:
            if component.is_root:
                continue

            neighbors = adjacency[
                component.id
            ]

            if not neighbors:
                continue

            component.parent = min(
                neighbors,
                key=lambda candidate_id: (
                    self._energy(
                        component.id,
                        candidate_id,
                        areas,
                        perimeters,
                        adjacency,
                        boundary_vertices,
                        reock_scores,
                        surface_types,
                        reock_union_cache,
                    ),
                    candidate_id,
                ),
            )

    def _trace_parent(self, start_id):
        components = {
            component.id: component
            for component in self.components
        }

        path = []
        positions = {}

        current_id = start_id

        while True:
            component = components[
                current_id
            ]

            if component.is_root:
                return {
                    'root': current_id,
                    'cycle': None,
                }

            if component.parent is None:
                return {
                    'root': None,
                    'cycle': None,
                }

            if current_id in positions:
                cycle_start = positions[
                    current_id
                ]

                return {
                    'root': None,
                    'cycle': tuple(
                        path[cycle_start:]
                    ),
                }

            positions[current_id] = len(path)
            path.append(current_id)

            current_id = component.parent

    def _collapse_parent_graph(self):
        components = {
            component.id: component
            for component in self.components
        }

        root_groups = {
            component.id: {component.id}
            for component in self.components
            if component.is_root
        }

        cycles = set()

        for component in self.components:
            if component.is_root:
                continue

            result = self._trace_parent(
                component.id
            )

            root_id = result['root']

            if root_id is not None:
                root_groups[
                    root_id
                ].add(component.id)

                continue

            cycle = result['cycle']

            if cycle is not None:
                cycles.add(
                    tuple(sorted(cycle))
                )

        consumed = set()
        new_groups = []

        # Everything whose parent-chain reaches a root
        # becomes part of that rooted component.
        for root_id, component_ids in root_groups.items():
            new_groups.append((
                component_ids,
                components[root_id].region_id,
            ))

            consumed.update(component_ids)

        # Only the actual cyclic cores are merged.
        # Tails feeding cycles remain free to choose again.
        for cycle in cycles:
            cycle_ids = set(cycle)

            if cycle_ids & consumed:
                continue

            new_groups.append((
                cycle_ids,
                None,
            ))

            consumed.update(cycle_ids)

        # Any unresolved non-cycle orphan remains by itself.
        for component in self.components:
            if component.id in consumed:
                continue

            new_groups.append((
                {component.id},
                component.region_id,
            ))

        changed = (
            len(new_groups)
            < len(self.components)
        )

        new_components = []

        for component_ids, region_id in new_groups:
            atom_ids = set()

            for component_id in component_ids:
                atom_ids.update(
                    components[
                        component_id
                    ].atom_ids
                )

            new_components.append(
                Component(
                    component_id=len(
                        new_components
                    ),
                    atom_ids=atom_ids,
                    region_id=region_id,
                )
            )

        self.components = new_components

        return changed

    def _resolve_orphans(self):
        pass_number = 0

        while True:
            orphan_count = sum(
                not component.is_root
                for component in self.components
            )

            if orphan_count == 0:
                return

            pass_number += 1

            self._choose_parents()

            changed = (
                self._collapse_parent_graph()
            )

            new_orphan_count = sum(
                not component.is_root
                for component in self.components
            )

            print(
                f'energy pass {pass_number}: '
                f'{orphan_count} -> '
                f'{new_orphan_count} orphans'
            )

            if not changed:
                raise RuntimeError(
                    'Energy resolution stalled with '
                    f'{new_orphan_count} orphans.'
                )

    def _assign_component_regions(self):
        for component in self.components:
            if component.region_id is None:
                continue

            for atom_id in component.atom_ids:
                self.atoms[atom_id].region_id = component.region_id
                self.orphan_ids.discard(atom_id)

    def resolve_orphans(self):
        """Run the optional automatic orphan-assignment energy algorithm."""
        if not self.atoms:
            raise ValueError('Cut borders into atoms before resolving orphans.')
        if not self.orphan_ids:
            return
        self._resolve_orphans()
        self._assign_component_regions()

    def atom_at(self, point):
        """Return the atom beneath a spherical point, including orphans."""
        if point is None:
            return None

        for atom in self.atoms:
            vertices = [
                self.vertices[vertex_id].point
                for vertex_id in atom.vertex_ids
            ]
            if spherical_polygon_contains(vertices, point):
                return atom.id
        return None

    def assign_orphan(self, orphan_id, target_id):
        """Attach an unassigned atom to the target atom's region.

        The target must already belong to a seeded or assigned region.
        """
        if orphan_id not in self.orphan_ids:
            raise ValueError('Source atom is not an orphan.')
        if not 0 <= target_id < len(self.atoms):
            raise ValueError('Target atom does not exist.')

        region_id = self.atoms[target_id].region_id
        if region_id is None:
            raise ValueError('Target atom has not been assigned to a region.')

        self.atoms[orphan_id].region_id = region_id
        self.orphan_ids.remove(orphan_id)

        # The cut operation starts with one component per atom. Keep
        # component labels in sync for optional later automatic resolution.
        for component in self.components:
            if orphan_id in component.atom_ids:
                component.region_id = region_id
                component.parent = None
                break

        return region_id

    def edge_separates_regions(self, edge):
        if (
            not edge.active
            or edge.halfedges is None
        ):
            return False

        first_id, second_id = edge.halfedges

        first_atom_id = self.halfedges[
            first_id
        ].atom_id

        second_atom_id = self.halfedges[
            second_id
        ].atom_id

        if (
            first_atom_id is None
            or second_atom_id is None
            or first_atom_id == second_atom_id
        ):
            return False

        first_region = self.atoms[
            first_atom_id
        ].region_id

        second_region = self.atoms[
            second_atom_id
        ].region_id

        return (
            first_region is not None
            and second_region is not None
            and first_region != second_region
        )

    def region_at(self, point):
        atom_id = self.atom_at(point)
        return None if atom_id is None else self.atoms[atom_id].region_id
