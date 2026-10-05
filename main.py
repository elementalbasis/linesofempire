import pygame
import moderngl
import cartopy.io.shapereader as shpreader
import math
import numpy as np

import matplotlib.pyplot as plt

# This is needed to convert QGIS line data into a list of coordinates
from shapely import get_parts



# Parameters
GAME_TITLE = 'Lines of Empire'
MAP_SCALE = '50m' # Options are: 10m, 50m, 110m
INITIAL_LON = 15.0
INITIAL_LAT = 50.0
INITIAL_ZOOM = 300.0

# These global variables will change when user presses a key.
center_lon = INITIAL_LON
center_lat = INITIAL_LAT
zoom = INITIAL_ZOOM



# pygame setup
pygame.init()
screen = pygame.display.set_mode(
        (1280, 720),
        # Double buffer means that there's a front buffer and a back buffer; the
        # front buffer is displayed to the user, and the back buffer is the one
        # that the program actually writes to. This is standard practice.
        pygame.RESIZABLE | pygame.OPENGL | pygame.DOUBLEBUF)
pygame.display.set_caption(GAME_TITLE)
clock = pygame.time.Clock()
running = True



# OpenGL context
ctx = moderngl.create_context()



# Get Natural Earth assets
land_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'land',
        )
lakes_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'lakes',
        )
coastlines_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'coastline',
        )
coastlines = list(
        shpreader.Reader(coastlines_filename).geometries()
        )
rivers_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'rivers_lake_centerlines',
        )
borders_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'cultural',
        name = 'admin_0_boundary_lines_land',
        )



# Helper function for coordinate transform
def lonlat_to_xyz(lon, lat):
    lon = math.radians(lon)
    lat = math.radians(lat)

    x = math.cos(lat) * math.cos(lon)
    y = math.cos(lat) * math.sin(lon)
    z = math.sin(lat)

    return (x, y, z)

# Helper function for the camera basis
def camera_basis(lon, lat):
    lon = math.radians(lon)
    lat = math.radians(lat)

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
            #math.cos(lat),
            math.sin(lat),
            )

    return east, north, forward



# Load the coastline data into a buffer

coast_vertices = []
for geom in coastlines:
    #for line in line_parts(geom):
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]

        for a, b in zip(xyz[:-1], xyz[1:]):
            coast_vertices.append(a)
            coast_vertices.append(b)
coast_vertices = np.asarray(
        coast_vertices,
        dtype = 'f4',
        )
coast_buffer = ctx.buffer(
        coast_vertices.tobytes()
        )



# Load my custom OpenGL shaders

VERTEX_SHADER_FILENAME = "vertex_shader.glsl"
FRAGMENT_SHADER_FILENAME = "fragment_shader.glsl"

with open(VERTEX_SHADER_FILENAME) as f:
    vertex_shader = f.read()
with open(FRAGMENT_SHADER_FILENAME) as f:
    fragment_shader = f.read()

program = ctx.program(
        vertex_shader = vertex_shader,
        fragment_shader = fragment_shader,
        )

# Load the coastline buffer into a vertex array
coast_vao = ctx.simple_vertex_array(
        program,
        coast_buffer,
        "in_pos",
        )



# Game loop
while running:
    # Handle events
    for event in pygame.event.get():
        # This occurs if the user clicks X to close the window.
        if event.type == pygame.QUIT:
            running = False
        '''
        if event.type == pygame.VIDEORESIZE:
            surface = pygame.display.set_mode((event.w, event.h),
                                              pygame.RESIZABLE)
        '''
    # fill the screen with a color to wipe away anything from last frame
    #screen.fill('purple')

    # OpenGL owns the buffer, so we clear like this instead.
    ctx.clear(1, 1, 1, 1)

    # Get window size
    width, height = pygame.display.get_window_size()

    # RENDER YOUR GAME HERE

    # Define the camera basis and pass it to the shaders
    east, north, forward = camera_basis(center_lon, center_lat)
    program["u_east"].value = east
    program["u_north"].value = north
    program["u_forward"].value = forward
    program["u_viewport"].value = (float(width), float(height))
    program["u_zoom"].value = zoom

    coast_vao.render(mode = moderngl.LINES)

    # flip() the display to put your work on screen
    #
    # Even though this function is called flip(), according to the PyGame
    # documentation, it simply updates the screen. The related update()
    # function updates only a selected portion of the screen. Neither of
    # these functions work if using OPENGL.
    #
    # For more context, it's called flip because it's meant to be used with
    # a double buffer. That's when there's a front buffer and a back buffer,
    # with the front buffer displayed to the user and the back buffer being the
    # one that the program actually writes to.
    pygame.display.flip()

    clock.tick(60) # limits FPS to 60

pygame.quit()
