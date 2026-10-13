import math
import numpy as np

from common import normalize, angular_distance


POINT_TOLERANCE = 1e-8
ARC_TOLERANCE = 1e-8


def same_point(a, b, tolerance=POINT_TOLERANCE):
    return np.linalg.norm(a - b) <= tolerance


def point_on_arc(point, start, end, tolerance=ARC_TOLERANCE):
    total = angular_distance(start, end)

    split = (
        angular_distance(start, point)
        + angular_distance(point, end)
    )

    return abs(split - total) <= tolerance


def arc_intersections(a, b, c, d):
    """
    Intersections of the minor great-circle arcs AB and CD.

    Returns zero, one, or (in degenerate cases) two unit vectors.
    Coincident great circles are currently ignored.
    """
    n1 = np.cross(a, b)
    n2 = np.cross(c, d)

    n1_length = np.linalg.norm(n1)
    n2_length = np.linalg.norm(n2)

    if n1_length < POINT_TOLERANCE:
        return []

    if n2_length < POINT_TOLERANCE:
        return []

    axis = np.cross(n1, n2)
    axis_length = np.linalg.norm(axis)

    # Same or nearly parallel great circle.
    if axis_length < POINT_TOLERANCE:
        return []

    point = axis / axis_length

    intersections = []

    for candidate in (point, -point):
        if (
            point_on_arc(candidate, a, b)
            and point_on_arc(candidate, c, d)
        ):
            if not any(
                same_point(candidate, existing)
                for existing in intersections
            ):
                intersections.append(candidate)

    return intersections


def tangent_direction(origin, destination):
    """
    Direction toward destination, projected into the tangent plane
    at origin.
    """
    tangent = (
        destination
        - np.dot(origin, destination) * origin
    )

    return normalize(tangent)


def outgoing_angle(origin, destination):
    """
    Polar angle of an outgoing spherical arc in origin's tangent plane.
    """
    if abs(origin[2]) < 0.9:
        reference = np.array((0.0, 0.0, 1.0))
    else:
        reference = np.array((1.0, 0.0, 0.0))

    east = normalize(
        np.cross(reference, origin)
    )

    north = np.cross(origin, east)

    tangent = tangent_direction(
        origin,
        destination,
    )

    return math.atan2(
        np.dot(tangent, north),
        np.dot(tangent, east),
    )


def spherical_polygon_winding(vertices, point):
    vertices = np.asarray(
        vertices,
        dtype=np.float64,
    )

    point = normalize(
        np.asarray(
            point,
            dtype=np.float64,
        )
    )

    next_vertices = np.roll(
        vertices,
        -1,
        axis=0,
    )

    ap = vertices @ point
    bp = next_vertices @ point

    numerator = np.cross(
        vertices,
        next_vertices,
    ) @ point

    denominator = (
        np.einsum(
            'ij,ij->i',
            vertices,
            next_vertices,
        )
        - ap * bp
    )

    return np.arctan2(
        numerator,
        denominator,
    ).sum()


def spherical_polygon_contains(vertices, point):
    # Faces produced by our half-edge walk have their interiors
    # consistently on the left, giving positive winding inside.
    return spherical_polygon_winding(
        vertices,
        point,
    ) > math.pi


def spherical_triangle_area(a, b, c):
    """
    Signed area of a spherical triangle on the unit sphere.
    """
    numerator = np.dot(
        a,
        np.cross(b, c),
    )

    denominator = (
        1.0
        + np.dot(a, b)
        + np.dot(b, c)
        + np.dot(c, a)
    )

    return 2.0 * math.atan2(
        numerator,
        denominator,
    )


def spherical_polygon_area(vertices):
    """
    Area on the unit sphere.

    The face walker produces consistently oriented simple faces,
    so fan accumulation is sufficient for the partition.
    """
    if len(vertices) < 3:
        return 0.0

    anchor = vertices[0]

    area = 0.0

    for i in range(1, len(vertices) - 1):
        area += spherical_triangle_area(
            anchor,
            vertices[i],
            vertices[i + 1],
        )

    return abs(area)
