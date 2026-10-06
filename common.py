import math

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
