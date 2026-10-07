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
            #- math.sin(lon),
            #- math.cos(lon),
            - math.sin(lon),
            math.cos(lon),
            0.0,
            ])

    north = np.array([
            - math.sin(lat) * math.cos(lon),
            - math.sin(lat) * math.sin(lon),
            math.cos(lat),
            #math.sin(lat),
            ])

    return east, north, forward
