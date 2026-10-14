import pygame
import math
import numpy as np

import config
from common import min_zoom, max_zoom, tangent_basis

class Camera:
    def __init__(self):
        self.lon = config.INITIAL_LON
        self.lat = config.INITIAL_LAT
        self.zoom = config.INITIAL_ZOOM

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
        self.zoom = max(min_zoom(width, height), min(max_zoom(width, height), self.zoom))

    def zoom_at(self, cursor, steps, width, height):
        """Zoom about the geographic location under the pointer."""
        if steps == 0:
            return
        anchor = self.screen_to_sphere(*cursor, width, height)
        self.zoom = max(
            min_zoom(width, height),
            min(max_zoom(width, height), self.zoom * config.ZOOM_WHEEL_FACTOR ** steps),
        )
        if anchor is not None:
            self.align_point_to_screen(anchor, cursor, width, height)

    def align_point_to_screen(self, anchor, cursor, width, height):
        """Reorient the globe to keep one world-space point beneath the cursor.

        Solve the two-degree-of-freedom orthographic projection. A bounded,
        damped Newton iteration avoids large jumps near the horizon and poles.
        """
        target_x, target_y = cursor
        # A sphere cannot project to a point outside its screen-space disk.
        dx = target_x - width / 2
        dy = target_y - height / 2
        radius = math.hypot(dx, dy)
        if radius > self.zoom:
            scale = self.zoom / radius
            target_x = width / 2 + dx * scale
            target_y = height / 2 + dy * scale

        anchor = np.asarray(anchor, dtype=np.float64)
        for _ in range(config.NAVIGATION_SOLVER_ITERATIONS):
            east, north, forward = self.basis()
            east_dot = float(np.dot(anchor, east))
            north_dot = float(np.dot(anchor, north))
            forward_dot = float(np.dot(anchor, forward))
            error = np.array([
                target_x - width / 2 - self.zoom * east_dot,
                target_y - height / 2 + self.zoom * north_dot,
            ])
            if np.linalg.norm(error) <= config.NAVIGATION_SOLVER_TOLERANCE:
                break

            lat = math.radians(self.lat)
            lon = math.radians(self.lon)
            radial = anchor[0] * math.cos(lon) + anchor[1] * math.sin(lon)
            # Derivatives w.r.t. longitude and latitude in radians.
            jacobian = self.zoom * np.array([
                [-radial, 0.0],
                [math.sin(lat) * east_dot, forward_dot],
            ])
            delta = np.linalg.lstsq(jacobian, error, rcond=None)[0]
            magnitude = np.linalg.norm(delta)
            if magnitude > config.NAVIGATION_MAX_STEP:
                delta *= config.NAVIGATION_MAX_STEP / magnitude

            old_lon, old_lat = self.lon, self.lat
            old_error = np.linalg.norm(error)
            accepted = False
            for n in range(config.NAVIGATION_LINE_SEARCH_STEPS):
                step = 0.5 ** n
                self.lon = (old_lon + math.degrees(delta[0] * step) + 180) % 360 - 180
                self.lat = max(-90.0, min(90.0, old_lat + math.degrees(delta[1] * step)))
                e, nvec, _ = self.basis()
                residual = np.array([
                    target_x - width / 2 - self.zoom * np.dot(anchor, e),
                    target_y - height / 2 + self.zoom * np.dot(anchor, nvec),
                ])
                if np.linalg.norm(residual) < old_error:
                    accepted = True
                    break
            if not accepted:
                self.lon, self.lat = old_lon, old_lat
                break

    def basis(self):
        return tangent_basis(self.lon, self.lat)

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

    def screen_to_sphere(self, screen_x, screen_y, width, height):
        x = (screen_x - width / 2) / self.zoom
        y = - (screen_y - height / 2) / self.zoom

        r_squared = x**2 + y**2
        if r_squared > 1.0:
            return None

        z = math.sqrt(1 - r_squared)

        east, north, forward = self.basis()

        point = east * x + north * y + forward * z
        point /= np.linalg.norm(point)

        return point
