import math
import numpy as np
import moderngl
from OpenGL.GL import GL_CLIP_DISTANCE0, GL_PROGRAM_POINT_SIZE
from PIL import Image

import config
from common import (
        read_file,
        tangent_basis,
        normalize,
        subdivide_spherical_triangle,
        )

GLOBE_VERTEX_SHADER = 'shaders/globe.vert'
HORIZON_GEOMETRY_SHADER = 'shaders/horizon.geom'
DISK_VERTEX_SHADER = 'shaders/disk.vert'
SOLID_FRAGMENT_SHADER = 'shaders/solid.frag'
VECTOR_GEOMETRY_SHADER = 'shaders/vector.geom'
VECTOR_VERTEX_SHADER = 'shaders/vector.vert'
POINT_VERTEX_SHADER = 'shaders/point.vert'
CITY_VERTEX_SHADER = 'shaders/city.vert'
CITY_FRAGMENT_SHADER = 'shaders/city.frag'
GEORASTER_VERTEX_SHADER = 'shaders/georaster.vert'
GEORASTER_FRAGMENT_SHADER = 'shaders/georaster.frag'

MINOR_CITY_TEXTURE = 'assets/circle.png'
MAJOR_CITY_TEXTURE = 'assets/circle_dot.png'
MAJOR_CAPITAL_TEXURE = 'assets/circle_star.png'

class Renderer:
    def __init__(self, world):
        self.show_lakes = True
        self.show_rivers = True
        self.show_admin_borders = True
        self.show_land = True
        self.show_ocean = True
        self.show_coastlines = True
        self.show_voronoi_seeds = True
        self.show_voronoi_edges = True
        self.show_cities = True
        self.show_georaster = False
        self.show_generated_borders = True
        self.show_regions = True
        self.show_atom_edges = True
        self.show_region_edges = True

        # OpenGL context
        self.ctx = moderngl.create_context()
        self.ctx.enable_direct(GL_PROGRAM_POINT_SIZE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (
                moderngl.SRC_ALPHA,
                moderngl.ONE_MINUS_SRC_ALPHA,
                )

        self._load_programs()
        self._load_camera_buffer()
        self._load_assets_vao(world)

        # Voronoi
        self.voronoi_seed_vao = None
        self.voronoi_edge_vao = None

        self.generated_borders_vao = None
        self.show_atom_edges = True
        self.atom_edges_vao = None
        self.show_region_edges = True
        self.region_edges_vao = None

        self.world = world
        #self.region_vaos = []
        self.highlight_region = None
        self.highlight_buffer = None
        self.highlight_vao = None

        self.georasters = [
                self._load_georaster(raster) for raster in world.georasters
                ]

        # Cities
        self.minor_city_texture = self._load_texture(MINOR_CITY_TEXTURE)
        self.major_city_texture = self._load_texture(MAJOR_CITY_TEXTURE)
        self.major_capital_texture = self._load_texture(MAJOR_CAPITAL_TEXURE)
        self.city_textures = {
                'circle': self.minor_city_texture,
                'circle+dot': self.major_city_texture,
                'circle+star': self.major_capital_texture,
                }

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
        georaster_vertex_shader = read_file(GEORASTER_VERTEX_SHADER)
        georaster_fragment_shader = read_file(GEORASTER_FRAGMENT_SHADER)

        self.vector_program = self.ctx.program(
            vertex_shader = vector_vertex_shader,
            geometry_shader = vector_geometry_shader,
            fragment_shader = solid_fragment_shader,
        )
        self.vector_program['u_max_arc'].value = config.MAX_VECTOR_ARC

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

        self.georaster_program = self.ctx.program(
                vertex_shader = georaster_vertex_shader,
                fragment_shader = georaster_fragment_shader,
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
                self.georaster_program,
                ]:
            program["Camera"].binding = self.camera_binding

    def _create_position_vao(self, assets_vertices, program):
        buffer = self.ctx.buffer(assets_vertices.tobytes())
        assets_vao = self.ctx.simple_vertex_array(program, buffer, 'in_pos')
        return assets_vao

    def _load_assets_vao(self, world):
        self.ocean_vao = self._create_position_vao(
                world.ocean_vertices,
                self.screen_program
                )
        self.coastlines_vao = self._create_position_vao(
                world.coastlines_vertices,
                self.vector_program
                )
        self.land_vao = self._create_position_vao(
                world.land_vertices,
                self.fill_program
                )
        self.lakes_vao = self._create_position_vao(
                world.lakes_vertices,
                self.fill_program
                )
        self.rivers_vao = self._create_position_vao(
                world.rivers_vertices,
                self.vector_program
                )
        self.admin_borders_vao = self._create_position_vao(
                world.admin_borders_vertices,
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

        # Highlighted region
        if self.show_regions:
            region = self.world.hovered_region
            self.update_highlight(region)
            if self.highlight_vao is not None:
                self.fill_program['u_color'].value = config.REGION_HOVER_COLOR
                self.highlight_vao.render(mode = moderngl.TRIANGLES)

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
        if self.show_admin_borders:
            self.vector_program['u_color'].value = config.ADMIN_BORDER_COLOR
            self.ctx.line_width = config.ADMIN_BORDER_THICKNESS
            self.admin_borders_vao.render(mode = moderngl.LINES)

        # Coastlines
        if self.show_coastlines:
            self.vector_program['u_color'].value = config.COAST_COLOR
            self.ctx.line_width = config.COAST_THICKNESS
            self.coastlines_vao.render(mode = moderngl.LINES)

        # Cities
        if self.show_cities:
            for city_vao, symbol in self.cities:
                texture = self.city_textures[symbol]
                texture.use(location = 0)
                self.city_program['u_texture'].value = 0
                city_vao.render(mode = moderngl.TRIANGLES)

        # GeoRaster
        if self.show_georaster:
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = (
                moderngl.SRC_ALPHA,
                moderngl.ONE_MINUS_SRC_ALPHA,
            )
            for texture, vao in self.georasters:
                texture.use(location=0)
                self.georaster_program['u_texture'].value = 0
                self.georaster_program['u_opacity'].value = 0.5
                vao.render(
                    mode=moderngl.TRIANGLES
                )

        # Voronoi edges
        if self.show_voronoi_edges and self.voronoi_edge_vao is not None:
            self.vector_program['u_color'].value = config.VORONOI_EDGE_COLOR
            self.ctx.line_width = config.VORONOI_EDGE_THICKNESS
            self.voronoi_edge_vao.render(mode = moderngl.LINES)

        # Voronoi seeds
        if self.show_voronoi_seeds and self.voronoi_seed_vao is not None:
            self.point_program['u_color'].value = config.VORONOI_SEED_COLOR
            self.point_program['u_point_size'].value = config.VORONOI_SEED_SIZE
            self.voronoi_seed_vao.render(mode = moderngl.POINTS)


        # Generated game borders
        if (
            self.show_generated_borders
            and self.generated_borders_vao is not None
        ):
            self.vector_program['u_color'].value = (
                config.GENERATED_BORDER_COLOR
            )

            self.ctx.line_width = (
                config.GENERATED_BORDER_THICKNESS
            )

            self.generated_borders_vao.render(
                mode=moderngl.LINES
            )

        # Atoms

        if self.show_atom_edges and self.atom_edges_vao is not None:
            self.vector_program['u_color'].value = config.ATOM_EDGE_COLOR
            self.ctx.line_width = config.ATOM_EDGE_THICKNESS
            self.atom_edges_vao.render(
                mode=moderngl.LINES
            )


        # Final regions

        if (
            self.show_region_edges
            and self.region_edges_vao is not None
        ):
            self.vector_program['u_color'].value = (
                config.REGION_EDGE_COLOR
            )

            self.ctx.line_width = (
                config.REGION_EDGE_THICKNESS
            )

            self.region_edges_vao.render(
                mode=moderngl.LINES
            )

        # Disable line clipping before calling imgui
        self.ctx.disable_direct(GL_CLIP_DISTANCE0)

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

    def update_highlight(self, region_id):
        if region_id == self.highlight_region:
            return

        if self.highlight_vao is not None:
            self.highlight_vao.release()
            self.highlight_vao = None

        if self.highlight_buffer is not None:
            self.highlight_buffer.release()
            self.highlight_buffer = None

        self.highlight_region = region_id

        if region_id is None:
            return

        partition = self.world.partition

        triangles = []

        for atom in partition.atoms:
            if atom.region_id != region_id:
                continue

            points = np.asarray(
                [
                    partition.vertices[
                        vertex_id
                    ].point
                    for vertex_id in atom.vertex_ids
                ],
                dtype=np.float64,
            )

            if len(points) < 3:
                continue

            center = normalize(
                points.mean(axis=0)
            )

            for a, b in zip(
                points,
                np.roll(points, -1, axis=0),
            ):
                triangles.extend(
                    subdivide_spherical_triangle(
                        center,
                        a,
                        b,
                        limit=config.MAX_TRIANGLE_ARC,
                    )
                )

        if not triangles:
            return

        vertices = np.asarray(
            triangles,
            dtype='f4',
        )

        self.highlight_buffer = self.ctx.buffer(
            vertices.tobytes()
        )

        self.highlight_vao = (
            self.ctx.simple_vertex_array(
                self.fill_program,
                self.highlight_buffer,
                'in_pos',
            )
        )

    def _load_georaster(self, raster):
        image = raster.image

        texture = self.ctx.texture(
            (
                raster.width,
                raster.height,
            ),
            4,
            image.tobytes(),
        )

        texture.filter = (
            moderngl.LINEAR,
            moderngl.LINEAR,
        )

        buffer = self.ctx.buffer(
            raster.vertices.tobytes()
        )

        vao = self.ctx.vertex_array(
            self.georaster_program,
            [
                (
                    buffer,
                    '3f 2f',
                    'in_pos',
                    'in_uv',
                )
            ],
        )

        return texture, vao

    def update_voronoi(self, world):
        seed_vertices = world.voronoi.seed_vertices
        if len(seed_vertices):
            self.voronoi_seed_vao = self._create_position_vao(
                    seed_vertices,
                    self.point_program,
                    )

        edge_vertices = world.voronoi.edge_vertices
        if len(edge_vertices):
            self.voronoi_edge_vao = self._create_position_vao(
                    edge_vertices,
                    self.vector_program,
                    )

    def update_generated_borders(self, world):
        if self.generated_borders_vao is not None:
            self.generated_borders_vao.release()
            self.generated_borders_vao = None

        vertices = world.border_vertices

        if len(vertices):
            self.generated_borders_vao = self._create_position_vao(
                vertices,
                self.vector_program,
            )

    def update_atoms(self, world):
        if self.atom_edges_vao is not None:
            self.atom_edges_vao.release()
            self.atom_edges_vao = None

        vertices = world.atom_edge_vertices

        if len(vertices):
            self.atom_edges_vao = self._create_position_vao(
                vertices,
                self.vector_program,
            )

    def update_regions(self, world):
        if self.region_edges_vao is not None:
            self.region_edges_vao.release()
            self.region_edges_vao = None

        vertices = world.region_edge_vertices

        if len(vertices):
            self.region_edges_vao = (
                self._create_position_vao(
                    vertices,
                    self.vector_program,
                )
            )

