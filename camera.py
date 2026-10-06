import pygame
import config
import math
import numpy as np

class Camera:
    def __init__(self):
        self.lon = config.INITIAL_LON
        self.lat = config.INITIAL_LAT
        self.zoom = config.INITIAL_ZOOM

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

    def update(self, dt, width, height):
        camera_speed = config.CAMERA_SPEED
        zoom_speed = config.ZOOM_SPEED

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            camera_speed *= config.FAST_SPEED_MULTIPLIER
            zoom_speed *= config.FAST_SPEED_MULTIPLIER
        if keys[pygame.K_SPACE]:
            camera_speed *= config.SLOW_SPEED_MULTIPLIER
            zoom_speed *= config.SLOW_SPEED_MULTIPLIER
        if keys[pygame.K_w]:
            self.lat += camera_speed * dt
        if keys[pygame.K_s]:
            self.lat -= camera_speed * dt
        if keys[pygame.K_a]:
            self.lon -= camera_speed * dt
        if keys[pygame.K_d]:
            self.lon += camera_speed * dt
        if keys[pygame.K_e]:
            self.zoom *= math.exp(zoom_speed * dt)
        if keys[pygame.K_q]:
            self.zoom *= math.exp(-zoom_speed * dt)

        # Constrain the coordinates
        self.lat = max(-90.0, min(90.0, self.lat))
        self.lon = (self.lon + 180.0) % 360.0 - 180.0

        # Constrain zoom
        self.zoom = max(Camera.min_zoom(width, height), min(Camera.max_zoom(width, height), self.zoom))



    def basis(self):
        lon = math.radians(self.lon)
        lat = math.radians(self.lat)

        forward = (
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
                )

        east = (
                #- math.sin(lon),
                #- math.cos(lon),
                - math.sin(lon),
                math.cos(lon),
                0.0,
                )

        north = (
                - math.sin(lat) * math.cos(lon),
                - math.sin(lat) * math.sin(lon),
                math.cos(lat),
                #math.sin(lat),
                )

        return east, north, forward

    def get_data(self, width, height):
        east, north, forward = self.basis()
        return np.array([
            *east, 0.0,
            *north, 0.0,
            *forward, 0.0,
            float(width), float(height), self.zoom, 0.0,
            ], dtype = 'f4')

    def write_to_buffer(self, camera_buffer, width, height):
        data = self.get_data(width, height)
        camera_buffer.write(data.tobytes())
