import math
import numpy as np
from enum import Enum, auto
from scipy.spatial import cKDTree

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


BOUNDARY_WEIGHT = {
    BoundaryKind.VORONOI: 1.0,
    BoundaryKind.RIVER: 2.0,
    BoundaryKind.ADMIN: 2.0,
    BoundaryKind.COAST: 4.0,
    BoundaryKind.SNAP: 0.0,
}

LAMBDA_CONTACT = 1.0
LAMBDA_BOUNDARY = 1.0

# Implement these once the required geometry/state exists.
LAMBDA_REOCK = 0.0
LAMBDA_TYPE = 0.0

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
        self._assign_roots(world)
        self._build_components()

        self._resolve_orphans()
        self._assign_component_regions()

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


    def _component_metrics(self):
        atom_to_component = {}

        for component in self.components:
            for atom_id in component.atom_ids:
                atom_to_component[atom_id] = component.id

        areas = {
            component.id: sum(
                self.atoms[atom_id].area
                for atom_id in component.atom_ids
            )
            for component in self.components
        }

        perimeters = {
            component.id: 0.0
            for component in self.components
        }

        adjacency = {
            component.id: {}
            for component in self.components
        }

        for edge in self.edges:
            if (
                not edge.active
                or edge.halfedges is None
            ):
                continue

            first_id, second_id = edge.halfedges

            atom_a = self.halfedges[
                first_id
            ].atom_id

            atom_b = self.halfedges[
                second_id
            ].atom_id

            component_a = (
                atom_to_component.get(atom_a)
                if atom_a is not None
                else None
            )

            component_b = (
                atom_to_component.get(atom_b)
                if atom_b is not None
                else None
            )

            # Internal edge of one component.
            if (
                component_a is not None
                and component_a == component_b
            ):
                continue

            if component_a is not None:
                perimeters[component_a] += edge.length

            if component_b is not None:
                perimeters[component_b] += edge.length

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

                contact['length'] += edge.length

                contact['weighted_length'] += (
                    boundary_weight
                    * edge.length
                )

        return (
            areas,
            perimeters,
            adjacency,
        )

    def _energy(
        self,
        orphan_id,
        candidate_id,
        areas,
        perimeters,
        adjacency,
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

        # Hooks for the next two terms.
        reock_energy = 0.0
        type_energy = 0.0

        return (
            contact_energy
            + boundary_energy
            + reock_energy
            + type_energy
        )

    def _choose_parents(self):
        (
            areas,
            perimeters,
            adjacency,
        ) = self._component_metrics()

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
                self.atoms[
                    atom_id
                ].region_id = component.region_id

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
