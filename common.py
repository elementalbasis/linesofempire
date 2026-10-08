import math
import numpy as np

import config



def min_zoom(width, height):
    return config.MIN_ZOOM_MULTIPLIER * min(width, height)

def max_zoom(width, height):
    return config.MAX_ZOOM_MULTIPLIER * min(width, height)

def lonlat_to_xyz(lon, lat):
    lon = math.radians(lon)
    lat = math.radians(lat)

    x = math.cos(lat) * math.cos(lon)
    y = math.cos(lat) * math.sin(lon)
    z = math.sin(lat)

    return (x, y, z)

def xyz_to_lonlat(x, y, z):
    lon = math.degrees(math.atan2(y, x))
    lat = math.degrees(math.asin(z))

    return (lon, lat)

def read_file(filename):
    with open(filename) as f:
        content = f.read()
    return content

def tangent_basis(lon, lat):
    lon = math.radians(lon)
    lat = math.radians(lat)
    forward = np.array([
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
            ])

    east = np.array([
            - math.sin(lon),
            math.cos(lon),
            0.0,
            ])

    north = np.array([
            - math.sin(lat) * math.cos(lon),
            - math.sin(lat) * math.sin(lon),
            math.cos(lat),
            ])

    return east, north, forward

def normalize(v):
    a = np.linalg.norm(v)
    if a == 0:
        return v * 0
    else:
        return v / a

def angular_distance(a, b):
    return math.acos(np.clip(np.dot(a, b), -1.0, 1.0))

def subdivide_spherical_triangle(a, b, c, limit):
    ab_angle = angular_distance(a, b)
    bc_angle = angular_distance(b, c)
    ca_angle = angular_distance(c, a)

    longest = max(
        ab_angle,
        bc_angle,
        ca_angle,
    )

    # Base case
    if longest <= limit:
        return [(a, b, c)]

    # Bisect the longest side.
    if ab_angle == longest:
        ab = normalize(a + b)

        return (
            subdivide_spherical_triangle(
                a, ab, c,
                limit,
            )
            +
            subdivide_spherical_triangle(
                ab, b, c,
                limit,
            )
        )

    elif bc_angle == longest:
        bc = normalize(b + c)

        return (
            subdivide_spherical_triangle(
                a, b, bc,
                limit,
            )
            +
            subdivide_spherical_triangle(
                a, bc, c,
                limit,
            )
        )

    else:
        ca = normalize(c + a)

        return (
            subdivide_spherical_triangle(
                a, b, ca,
                limit,
            )
            +
            subdivide_spherical_triangle(
                ca, b, c,
                limit,
            )
        )
