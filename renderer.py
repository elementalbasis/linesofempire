import math
import numpy as np
import moderngl
from OpenGL.GL import GL_CLIP_DISTANCE0, GL_PROGRAM_POINT_SIZE
from PIL import Image

import config
from common import read_file, tangent_basis

GLOBE_VERTEX_SHADER = 'shaders/globe.vert'
HORIZON_GEOMETRY_SHADER = 'shaders/horizon.geom'
DISK_VERTEX_SHADER = 'shaders/disk.vert'
SOLID_FRAGMENT_SHADER = 'shaders/solid.frag'
VECTOR_GEOMETRY_SHADER = 'shaders/vector.geom'
VECTOR_VERTEX_SHADER = 'shaders/vector.vert'
POINT_VERTEX_SHADER = 'shaders/point.vert'
CITY_VERTEX_SHADER = 'shaders/city.vert'
CITY_FRAGMENT_SHADER = 'shaders/city.frag'

MINOR_CITY_TEXTURE = 'assets/circle.png'
MAJOR_CITY_TEXTURE = 'assets/circle_dot.png'
CAPITAL_CITY_TEXTURE = 'assets/circle_star.png'

class Renderer:
    def __init__(self, world):
        self.show_lakes = True
        self.show_rivers = True
        self.show_borders = True
        self.show_land = True
        self.show_ocean = True
        self.show_coastlines = True
        self.show_voronoi = True
        self.show_cities = True

        # OpenGL context
        self.ctx = moderngl.create_context()
        self.ctx.enable_direct(GL_PROGRAM_POINT_SIZE)

        self._load_programs()
        self._load_camera_buffer()
        self._load_assets_vao(world)

        # Voronoi
        self.voronoi_seed_vao = None
        self.voronoi_edge_vao = None

        self.world = world
        self.region_vaos = []

        # Cities
        self.minor_city_texture = self._load_texture(MINOR_CITY_TEXTURE)
        self.major_city_texture = self._load_texture(MAJOR_CITY_TEXTURE)
        self.capital_city_texture = self._load_texture(CAPITAL_CITY_TEXTURE)

    # Load my custom OpenGL shaders
    def _load_programs(self):
        globe_vertex_shader = read_file(GLOBE_VERTEX_SHADER)
        horizon_geometry_shader = read_file(HORIZON_GEOMETRY_SHADER)
        disk_vertex_shader = read_file(DISK_VERTEX_SHADER)
        solid_fragment_shader = read_file(SOLID_FRAGMENT_SHADER)
        vector_geometry_shader = read_file(VECTOR_GEOMETRY_SHADER)
        vector_vertex_shader = read_file(VECTOR_VERTEX_SHADER)
        point_vertex_shader = read_file(POINT_VERTEX_SHADER)
        city_vertex_shader = read_file(CITY_VERTEX_SHADER)
        city_fragment_shader = read_file(CITY_FRAGMENT_SHADER)

        self.vector_program = self.ctx.program(
            vertex_shader = vector_vertex_shader,
            geometry_shader = vector_geometry_shader,
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

        self.point_program = self.ctx.program(
                vertex_shader = point_vertex_shader,
                fragment_shader = solid_fragment_shader,
                )

        self.city_program = self.ctx.program(
                vertex_shader = city_vertex_shader,
                fragment_shader = city_fragment_shader,
                )

    def _load_camera_buffer(self):
        # Create the shared camera Uniform Buffer Object
        self.camera_binding = 0
        self.camera_buffer = self.ctx.buffer(reserve = 64)
        self.camera_buffer.bind_to_uniform_block(self.camera_binding)

        for program in [
                self.vector_program,
                self.fill_program,
                self.screen_program,
                self.point_program,
                self.city_program,
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

        self.cities = []
        for index, row in world.cities_df.iterrows():
            lon = row['Lon']
            lat = row['Lat']
            city_vertices = Renderer.city_quad(
                    lon, lat, config.CITY_SYMBOL_RADIUS)
            buffer = self.ctx.buffer(city_vertices.tobytes())
            city_vao = self.ctx.vertex_array(
                self.city_program,
                [(
                    buffer,
                    '3f 2f',
                    'in_pos',
                    'in_uv',
                )],
            )
            self.cities.append((city_vao, row['Symbol']))

    def render(self, camera, width, height):
        self.ctx.viewport = (0, 0, width, height)

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

        # Selected region
        region = self.world.hovered_region
        if region is not None:
            vao = self.region_vaos[region.id]
            if vao is not None:
                self.fill_program['u_color'].value = config.REGION_HOVER_COLOR
                vao.render(mode = moderngl.TRIANGLES)

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

        # Cities
        if self.show_cities:
            for city_vao, symbol in self.cities:
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = (
                        moderngl.SRC_ALPHA,
                        moderngl.ONE_MINUS_SRC_ALPHA,
                        )
                texture = {
                        'circle+star': self.capital_city_texture,
                        'circle+dot': self.major_city_texture,
                        'circle': self.minor_city_texture,
                        }[symbol]
                texture.use(location = 0)
                self.city_program['u_texture'].value = 0
                city_vao.render(mode = moderngl.TRIANGLES)

        # Voronoi edges
        if self.show_voronoi and self.voronoi_edge_vao is not None:
            self.vector_program['u_color'].value = config.VORONOI_EDGE_COLOR
            self.vector_program['u_max_arc'].value = config.MAX_VECTOR_ARC
            self.ctx.line_width = config.VORONOI_EDGE_THICKNESS
            self.voronoi_edge_vao.render(mode = moderngl.LINES)

        # Voronoi seeds
        if self.show_voronoi and self.voronoi_seed_vao is not None:
            self.point_program['u_color'].value = config.VORONOI_SEED_COLOR
            self.point_program['u_point_size'].value = config.VORONOI_SEED_SIZE
            self.voronoi_seed_vao.render(mode = moderngl.POINTS)

        # Disable line clipping before calling imgui
        self.ctx.disable_direct(GL_CLIP_DISTANCE0)

    def update_voronoi(self, world):
        seed_vertices = world.voronoi.seed_vertices
        if len(seed_vertices):
            self.voronoi_seed_vao = self._get_assets_vao(
                    seed_vertices,
                    self.point_program,
                    )

        edge_vertices = world.voronoi.edge_vertices
        if len(edge_vertices):
            self.voronoi_edge_vao = self._get_assets_vao(
                    edge_vertices,
                    self.vector_program,
                    )

    def _load_texture(self, filename):
        image = Image.open(filename).convert('RGBA')

        # OpenGL's texture origin is opposite Pillow's
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        texture = self.ctx.texture(image.size, 4, image.tobytes())
        texture.build_mipmaps()

        texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)

        return texture

    def city_quad(lon, lat, radius):
        east, north, center = tangent_basis(lon, lat)
        def point(x, y):
            p = (
                center
                + math.tan(radius) * x * east
                + math.tan(radius) * y * north
            )
            return p / np.linalg.norm(p)
        bl = point(-1, -1)
        br = point(+1, -1)
        tl = point(-1, +1)
        tr = point(+1, +1)
        return np.asarray([
            # xyz, uv
            *bl, 0.0, 0.0,
            *br, 1.0, 0.0,
            *tr, 1.0, 1.0,
            *bl, 0.0, 0.0,
            *tr, 1.0, 1.0,
            *tl, 0.0, 1.0,
            ], dtype='f4')

    def update_regions(self, world):
        for vao in self.region_vaos:
            if vao is not None:
                vao.release()

        self.region_vaos = []
        for region in world.regions:
            if len(region.vertices):
                vao = self._get_assets_vao(
                        region.vertices,
                        self.fill_program,
                        )
            else:
                vao = None

            self.region_vaos.append(vao)
