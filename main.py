import pygame
import moderngl
import cartopy.io.shapereader as shpreader
import math
import numpy as np

# ImGui
import imgui
from imgui.integrations.pygame import PygameRenderer
from imgui.integrations.opengl import ProgrammablePipelineRenderer

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb

# This is needed to convert QGIS data into a list of points
from shapely import get_parts, constrained_delaunay_triangles



# Parameters
GAME_TITLE = 'Lines of Empire'
MAP_SCALE = '50m' # Options are: 10m, 50m, 110m
INITIAL_LON = 15.0
INITIAL_LAT = 50.0
INITIAL_ZOOM = 300.0
CAMERA_SPEED = 60.0 # degrees per second
SPEED_MULTIPLIER = 3.0
ZOOM_SPEED = 1.5
MIN_ZOOM_MULTIPLIER = 0.35
MAX_ZOOM_MULTIPLIER = 8

# Map colors and styling
LAND_COLOR = to_rgb('#d8c99b')
OCEAN_COLOR = to_rgb('#557c7a')
COAST_COLOR = to_rgb('#282620')
OUTSIDE_COLOR = to_rgb('#18191b')
BORDER_COLOR = to_rgb('#635441')
COAST_THICKNESS = 2.0
RIVER_THICKNESS = 1.25
BORDER_THICKNESS = 1.0
#PROVINCE_THICKNESS = 0.75
HORIZON_THICKNESS = 2.0
OCEAN_SEGMENTS = 256

# Bools for whether to show various features
show_lakes = True
show_rivers = True
show_borders = True

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

# ImGui setup
class ModernPygameRenderer(
        ProgrammablePipelineRenderer,
        PygameRenderer
        ):
    pass
imgui.create_context()
renderer = ModernPygameRenderer()
io = imgui.get_io()
io.display_size = pygame.display.get_window_size()



# Get Natural Earth assets
land_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'land',
        )
land = list(
        shpreader.Reader(land_filename).geometries()
        )
lakes_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'physical',
        name = 'lakes',
        )
lakes = list(
        shpreader.Reader(lakes_filename).geometries()
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
rivers = list(
        shpreader.Reader(rivers_filename).geometries()
        )
borders_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'cultural',
        name = 'admin_0_boundary_lines_land',
        )
borders = list(
        shpreader.Reader(borders_filename).geometries()
        )
'''
provinces_filename = shpreader.natural_earth(
        resolution = MAP_SCALE,
        category = 'cultural',
        name = 'admin_1_boundary_lines_land',
        )
provinces = list(
        shpreader.Reader(provinces_filename).geometries()
        )
'''


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
            math.cos(lat),
            #math.sin(lat),
            )

    return east, north, forward



# Helper functions for zoom

def min_zoom(width, height):
    return MIN_ZOOM_MULTIPLIER * min(width, height)

def max_zoom(width, height):
    return MAX_ZOOM_MULTIPLIER * min(width, height)



# Load my custom OpenGL shaders

VERTEX_SHADER_FILENAME = 'vertex_shader.glsl'
FRAGMENT_SHADER_FILENAME = 'fragment_shader.glsl'
CIRCLE_VERTEX_SHADER_FILENAME = 'circle_vertex_shader.glsl'

with open(VERTEX_SHADER_FILENAME) as f:
    vertex_shader = f.read()
with open(FRAGMENT_SHADER_FILENAME) as f:
    fragment_shader = f.read()
with open(CIRCLE_VERTEX_SHADER_FILENAME) as f:
    circle_vertex_shader = f.read()

program = ctx.program(
        vertex_shader = vertex_shader,
        fragment_shader = fragment_shader,
        )



# Create ocean disk out of triangles
ocean_vertices = [(0.0, 0.0)] # Start with the origin
for i in range(OCEAN_SEGMENTS + 1):
    angle = 2 * math.pi * i / OCEAN_SEGMENTS
    ocean_vertices.append((math.cos(angle), math.sin(angle)))
ocean_vertices = np.asarray(
        ocean_vertices,
        dtype = 'f4'
        )

ocean_program = ctx.program(
        vertex_shader = circle_vertex_shader,
        fragment_shader = fragment_shader,
        )
ocean_buffer = ctx.buffer(
        ocean_vertices.tobytes()
        )
ocean_vao = ctx.simple_vertex_array(
        ocean_program,
        ocean_buffer,
        'in_pos',
        )




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

# Load the coastline buffer into a vertex array
coast_vao = ctx.simple_vertex_array(
        program,
        coast_buffer,
        'in_pos',
        )



# Load land polygons
land_vertices = []
for geom in land:
    for polygon in get_parts(geom):
        for triangle in get_parts(constrained_delaunay_triangles(polygon)):
            # These coordinates come in a closed loop, so we must exclude the
            # last element.
            coords = list(triangle.exterior.coords)[:-1]

            for lon, lat in coords:
                land_vertices.append(
                        lonlat_to_xyz(lon, lat)
                        )
land_vertices = np.asarray(
        land_vertices,
        dtype = 'f4',
        )
land_buffer = ctx.buffer(
        land_vertices.tobytes()
        )

# Load the land buffer into a vertex array
land_vao = ctx.simple_vertex_array(
        program,
        land_buffer,
        'in_pos',
        )



# Load lake polygons
lake_vertices = []
for geom in lakes:
    for polygon in get_parts(geom):
        for triangle in get_parts(constrained_delaunay_triangles(polygon)):
            coords = list(triangle.exterior.coords)[:-1]

            for lon, lat in coords:
                lake_vertices.append(
                        lonlat_to_xyz(lon, lat)
                        )
lake_vertices = np.asarray(
        lake_vertices,
        dtype = 'f4',
        )
lake_buffer = ctx.buffer(
        lake_vertices.tobytes()
        )
lake_vao = ctx.simple_vertex_array(
        program,
        lake_buffer,
        'in_pos',
        )



# Load river lines
river_vertices = []
for geom in rivers:
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]

        for a, b in zip(xyz[:-1], xyz[1:]):
            river_vertices.append(a)
            river_vertices.append(b)

river_vertices = np.asarray(
        river_vertices,
        dtype = 'f4'
        )
river_buffer = ctx.buffer(
        river_vertices.tobytes()
        )
river_vao = ctx.simple_vertex_array(
        program,
        river_buffer,
        'in_pos'
        )



# Load international borders
border_vertices = []
for geom in borders:
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]
        for a, b in zip(xyz[:-1], xyz[1:]):
            border_vertices.append(a)
            border_vertices.append(b)
border_vertices = np.asarray(
        border_vertices,
        dtype = 'f4'
        )
border_buffer = ctx.buffer(
        border_vertices.tobytes()
        )
border_vao = ctx.simple_vertex_array(
        program,
        border_buffer,
        'in_pos',
        )



# Load province borders
'''
province_vertices = []
for geom in provinces:
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [lonlat_to_xyz(lon, lat) for lon, lat in coords]
        for a, b in zip(xyz[:-1], xyz[1:]):
            province_vertices.append(a)
            province_vertices.append(b)
province_vertices = np.asarray(
        province_vertices,
        dtype = 'f4'
        )
province_buffer = ctx.buffer(
        province_vertices.tobytes()
        )
province_vao = ctx.simple_vertex_array(
        program,
        province_buffer,
        'in_pos',
        )
'''


# Game loop
while running:
    # Get window size
    width, height = pygame.display.get_window_size()

    # Handle camera movement
    dt = clock.tick(60) / 1000.0
    speed = CAMERA_SPEED
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
        speed *= SPEED_MULTIPLIER
    if keys[pygame.K_w]:
        center_lat += speed * dt
    if keys[pygame.K_s]:
        center_lat -= speed * dt
    if keys[pygame.K_a]:
        center_lon -= speed * dt
    if keys[pygame.K_d]:
        center_lon += speed * dt
    if keys[pygame.K_e]:
        zoom *= math.exp(ZOOM_SPEED * dt)
    if keys[pygame.K_q]:
        zoom *= math.exp(-ZOOM_SPEED * dt)

    # Constrain the coordinates
    center_lat = max(-90.0, min(90.0, center_lat))
    center_lon = (center_lon + 180.0) % 360.0 - 180.0

    # Constrain zoom
    zoom = max(min_zoom(width, height), min(max_zoom(width, height), zoom))

    # Handle events
    for event in pygame.event.get():
        # Pass the event to ImGui
        renderer.process_event(event)

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



    # Handle the menu bar
    renderer.process_inputs()
    imgui.new_frame()
    if imgui.begin_main_menu_bar():
        if imgui.begin_menu('View', True):
            _, show_lakes = imgui.menu_item(
                    'Lakes', '', show_lakes, True
                    )
            _, show_rivers = imgui.menu_item(
                    'Rivers', '', show_rivers, True
                    )
            _, show_borders = imgui.menu_item(
                    'Borders', '', show_borders, True
                    )
            imgui.end_menu()
        imgui.end_main_menu_bar()




    # OpenGL owns the buffer, so we clear like this instead.
    ctx.clear(*OUTSIDE_COLOR)

    # Define the camera basis and pass it to the shaders
    east, north, forward = camera_basis(center_lon, center_lat)
    program['u_east'].value = east
    program['u_north'].value = north
    program['u_forward'].value = forward
    program['u_viewport'].value = (float(width), float(height))
    program['u_zoom'].value = zoom

    # Ocean
    ocean_program['u_viewport'].value = (float(width), float(height))
    ocean_program['u_zoom'].value = zoom
    ocean_program['u_color'].value = OCEAN_COLOR
    ocean_vao.render(mode = moderngl.TRIANGLE_FAN)

    # Land
    program['u_color'].value = LAND_COLOR
    land_vao.render(mode = moderngl.TRIANGLES)

    # Lakes
    if show_lakes:
        program['u_color'].value = OCEAN_COLOR
        lake_vao.render(mode = moderngl.TRIANGLES)

    # Rivers
    if show_rivers:
        program['u_color'].value = OCEAN_COLOR
        ctx.line_width = RIVER_THICKNESS
        river_vao.render(mode = moderngl.LINES)

    # Borders
    if show_borders:
        program['u_color'].value = BORDER_COLOR
        ctx.line_width = BORDER_THICKNESS
        border_vao.render(mode = moderngl.LINES)

    # Coastlines
    program['u_color'].value = COAST_COLOR
    ctx.line_width = COAST_THICKNESS
    coast_vao.render(mode = moderngl.LINES)

    # Render the top menu on top of the world
    imgui.render()
    renderer.render(imgui.get_draw_data())

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

renderer.shutdown()
pygame.quit()
