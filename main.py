import pygame
import moderngl
import cartopy.io.shapereader as shpreader
import math
import numpy as np

from OpenGL.GL import GL_CLIP_DISTANCE0

# ImGui
import imgui
from imgui.integrations.pygame import PygameRenderer
from imgui.integrations.opengl import ProgrammablePipelineRenderer

from matplotlib.colors import to_rgb

# This is needed to convert QGIS data into a list of points
from shapely import get_parts, constrained_delaunay_triangles



# Import this project's files
import config
from camera import Camera



# Bools for whether to show various features
show_lakes = True
show_rivers = True
show_borders = True



# pygame setup
pygame.init()
screen = pygame.display.set_mode(
        (1280, 720),
        # Double buffer means that there's a front buffer and a back buffer; the
        # front buffer is displayed to the user, and the back buffer is the one
        # that the program actually writes to. This is standard practice.
        pygame.RESIZABLE | pygame.OPENGL | pygame.DOUBLEBUF)
pygame.display.set_caption(config.GAME_TITLE)
clock = pygame.time.Clock()
running = True

# Initialize camera
camera = Camera()

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
        resolution = config.MAP_SCALE,
        category = 'physical',
        name = 'land',
        )
land = list(
        shpreader.Reader(land_filename).geometries()
        )
lakes_filename = shpreader.natural_earth(
        resolution = config.MAP_SCALE,
        category = 'physical',
        name = 'lakes',
        )
lakes = list(
        shpreader.Reader(lakes_filename).geometries()
        )
coastlines_filename = shpreader.natural_earth(
        resolution = config.MAP_SCALE,
        category = 'physical',
        name = 'coastline',
        )
coastlines = list(
        shpreader.Reader(coastlines_filename).geometries()
        )
rivers_filename = shpreader.natural_earth(
        resolution = config.MAP_SCALE,
        category = 'physical',
        name = 'rivers_lake_centerlines',
        )
rivers = list(
        shpreader.Reader(rivers_filename).geometries()
        )
borders_filename = shpreader.natural_earth(
        resolution = config.MAP_SCALE,
        category = 'cultural',
        name = 'admin_0_boundary_lines_land',
        )
borders = list(
        shpreader.Reader(borders_filename).geometries()
        )






# Load my custom OpenGL shaders

with open(config.GLOBE_VERTEX_SHADER) as f:
    globe_vertex_shader = f.read()
with open(config.HORIZON_GEOMETRY_SHADER) as f:
    horizon_geometry_shader = f.read()
with open(config.DISK_VERTEX_SHADER) as f:
    disk_vertex_shader = f.read()
with open(config.SOLID_FRAGMENT_SHADER) as f:
    solid_fragment_shader = f.read()

vector_program = ctx.program(
    vertex_shader = globe_vertex_shader,
    fragment_shader = solid_fragment_shader,
)

fill_program = ctx.program(
    vertex_shader = globe_vertex_shader,
    geometry_shader = horizon_geometry_shader,
    fragment_shader = solid_fragment_shader,
)

screen_program = ctx.program(
    vertex_shader = disk_vertex_shader,
    fragment_shader = solid_fragment_shader,
)

# Create the shared camera Uniform Buffer Object
CAMERA_BINDING = 0
camera_buffer = ctx.buffer(reserve = 64)
camera_buffer.bind_to_uniform_block(CAMERA_BINDING)

vector_program['Camera'].binding = CAMERA_BINDING
fill_program['Camera'].binding = CAMERA_BINDING
screen_program['Camera'].binding = CAMERA_BINDING



# Create ocean disk out of triangles
ocean_vertices = [(0.0, 0.0)] # Start with the origin
for i in range(config.OCEAN_SEGMENTS + 1):
    angle = 2 * math.pi * i / config.OCEAN_SEGMENTS
    ocean_vertices.append((math.cos(angle), math.sin(angle)))
ocean_vertices = np.asarray(
        ocean_vertices,
        dtype = 'f4'
        )
ocean_buffer = ctx.buffer(
        ocean_vertices.tobytes()
        )
ocean_vao = ctx.simple_vertex_array(
        screen_program,
        ocean_buffer,
        'in_pos',
        )



# Load the coastline data into a buffer

coast_vertices = []
for geom in coastlines:
    #for line in line_parts(geom):
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [Camera.lonlat_to_xyz(lon, lat) for lon, lat in coords]

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
        #program,
        vector_program,
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
                        Camera.lonlat_to_xyz(lon, lat)
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
        #program,
        fill_program,
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
                        Camera.lonlat_to_xyz(lon, lat)
                        )
lake_vertices = np.asarray(
        lake_vertices,
        dtype = 'f4',
        )
lake_buffer = ctx.buffer(
        lake_vertices.tobytes()
        )
lake_vao = ctx.simple_vertex_array(
        #program,
        fill_program,
        lake_buffer,
        'in_pos',
        )



# Load river lines
river_vertices = []
for geom in rivers:
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [Camera.lonlat_to_xyz(lon, lat) for lon, lat in coords]

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
        #program,
        vector_program,
        river_buffer,
        'in_pos'
        )



# Load international borders
border_vertices = []
for geom in borders:
    for line in get_parts(geom):
        coords = list(line.coords)
        xyz = [Camera.lonlat_to_xyz(lon, lat) for lon, lat in coords]
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
        #program,
        vector_program,
        border_buffer,
        'in_pos',
        )



# Game loop
while running:
    # Get window size
    width, height = pygame.display.get_window_size()

    # Handle camera movement
    dt = clock.tick(60) / 1000.0
    camera.update(dt, width, height)

    # Handle events
    for event in pygame.event.get():
        # Pass the event to ImGui
        renderer.process_event(event)

        # This occurs if the user clicks X to close the window.
        if event.type == pygame.QUIT:
            running = False

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

    # Write camera data to buffer
    camera.write_to_buffer(camera_buffer, width, height)

    # Clear the screen
    ctx.clear(*config.OUTSIDE_COLOR)

    # Ocean
    screen_program['u_color'].value = config.OCEAN_COLOR
    ocean_vao.render(mode = moderngl.TRIANGLE_FAN)

    # Land
    fill_program['u_color'].value = config.LAND_COLOR
    land_vao.render(mode = moderngl.TRIANGLES)

    # Lakes
    if show_lakes:
        fill_program['u_color'].value = config.OCEAN_COLOR
        lake_vao.render(mode = moderngl.TRIANGLES)

    # Enable line clipping
    ctx.enable_direct(GL_CLIP_DISTANCE0)

    # Rivers
    if show_rivers:
        vector_program['u_color'].value = config.OCEAN_COLOR
        ctx.line_width = config.RIVER_THICKNESS
        river_vao.render(mode = moderngl.LINES)

    # Borders
    if show_borders:
        vector_program['u_color'].value = config.BORDER_COLOR
        ctx.line_width = config.BORDER_THICKNESS
        border_vao.render(mode = moderngl.LINES)

    # Coastlines
    vector_program['u_color'].value = config.COAST_COLOR
    ctx.line_width = config.COAST_THICKNESS
    coast_vao.render(mode = moderngl.LINES)

    # Disable line clipping before calling imgui
    ctx.disable_direct(GL_CLIP_DISTANCE0)

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

    #clock.tick(60) # limits FPS to 60

renderer.shutdown()
pygame.quit()
