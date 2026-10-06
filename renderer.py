import moderngl
from OpenGL.GL import GL_CLIP_DISTANCE0

import config
from common import read_file

GLOBE_VERTEX_SHADER = 'shaders/globe.vert'
HORIZON_GEOMETRY_SHADER = 'shaders/horizon.geom'
DISK_VERTEX_SHADER = 'shaders/disk.vert'
SOLID_FRAGMENT_SHADER = 'shaders/solid.frag'

class Renderer:
    def __init__(self, world):
        self.show_lakes = True
        self.show_rivers = True
        self.show_borders = True
        self.show_land = True
        self.show_ocean = True
        self.show_coastlines = True

        # OpenGL context
        self.ctx = moderngl.create_context()

        self._load_programs()
        self._load_camera_buffer()
        self._load_assets_vao(world)

    # Load my custom OpenGL shaders
    def _load_programs(self):
        globe_vertex_shader = read_file(GLOBE_VERTEX_SHADER)
        horizon_geometry_shader = read_file(HORIZON_GEOMETRY_SHADER)
        disk_vertex_shader = read_file(DISK_VERTEX_SHADER)
        solid_fragment_shader = read_file(SOLID_FRAGMENT_SHADER)

        self.vector_program = self.ctx.program(
            vertex_shader = globe_vertex_shader,
            fragment_shader = solid_fragment_shader,
        )

        self.fill_program = self.ctx.program(
            vertex_shader = globe_vertex_shader,
            geometry_shader = horizon_geometry_shader,
            fragment_shader = solid_fragment_shader,
        )

        self.screen_program = self.ctx.program(
            vertex_shader = disk_vertex_shader,
            fragment_shader = solid_fragment_shader,
        )

    def _load_camera_buffer(self):
        # Create the shared camera Uniform Buffer Object
        self.camera_binding = 0
        self.camera_buffer = self.ctx.buffer(reserve = 64)
        self.camera_buffer.bind_to_uniform_block(self.camera_binding)

        for program in [
                self.vector_program,
                self.fill_program,
                self.screen_program
                ]:
            program["Camera"].binding = self.camera_binding

    def _get_assets_vao(self, assets_vertices, program):
        buffer = self.ctx.buffer(assets_vertices.tobytes())
        assets_vao = self.ctx.simple_vertex_array(program, buffer, 'in_pos')
        return assets_vao

    def _load_assets_vao(self, world):
        self.ocean_vao = self._get_assets_vao(
                world.ocean_vertices,
                self.screen_program
                )
        self.coastlines_vao = self._get_assets_vao(
                world.coastlines_vertices,
                self.vector_program
                )
        self.land_vao = self._get_assets_vao(
                world.land_vertices,
                self.fill_program
                )
        self.lakes_vao = self._get_assets_vao(
                world.lakes_vertices,
                self.fill_program
                )
        self.rivers_vao = self._get_assets_vao(
                world.rivers_vertices,
                self.vector_program
                )
        self.borders_vao = self._get_assets_vao(
                world.borders_vertices,
                self.vector_program
                )

    def render(self, camera, width, height):
        # Write camera data to buffer
        camera.write_to_buffer(self.camera_buffer, width, height)

        # Clear the screen
        self.ctx.clear(*config.OUTSIDE_COLOR)

        # Ocean
        if self.show_ocean:
            self.screen_program['u_color'].value = config.OCEAN_COLOR
            self.ocean_vao.render(mode = moderngl.TRIANGLE_FAN)

        # Land
        if self.show_land:
            self.fill_program['u_color'].value = config.LAND_COLOR
            self.land_vao.render(mode = moderngl.TRIANGLES)

        # Lakes
        if self.show_lakes:
            self.fill_program['u_color'].value = config.OCEAN_COLOR
            self.lakes_vao.render(mode = moderngl.TRIANGLES)

        # Enable line clipping
        self.ctx.enable_direct(GL_CLIP_DISTANCE0)

        # Rivers
        if self.show_rivers:
            self.vector_program['u_color'].value = config.OCEAN_COLOR
            self.ctx.line_width = config.RIVER_THICKNESS
            self.rivers_vao.render(mode = moderngl.LINES)

        # Borders
        if self.show_borders:
            self.vector_program['u_color'].value = config.BORDER_COLOR
            self.ctx.line_width = config.BORDER_THICKNESS
            self.borders_vao.render(mode = moderngl.LINES)

        # Coastlines
        if self.show_coastlines:
            self.vector_program['u_color'].value = config.COAST_COLOR
            self.ctx.line_width = config.COAST_THICKNESS
            self.coastlines_vao.render(mode = moderngl.LINES)

        # Disable line clipping before calling imgui
        self.ctx.disable_direct(GL_CLIP_DISTANCE0)
