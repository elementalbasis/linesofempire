import pygame
from enum import Enum, auto

# ImGui
import imgui
from imgui.integrations.pygame import PygameRenderer
from imgui.integrations.opengl import ProgrammablePipelineRenderer

# Import this project's files
import config
from camera import Camera
from world import World
from renderer import Renderer



# pygame setup
pygame.init()
screen = pygame.display.set_mode(
        (config.INITIAL_SCREEN_WIDTH, config.INITIAL_SCREEN_HEIGHT),
        # Double buffer means that there's a front buffer and a back buffer; the
        # front buffer is displayed to the user, and the back buffer is the one
        # that the program actually writes to. This is standard practice.
        pygame.RESIZABLE | pygame.OPENGL | pygame.DOUBLEBUF)
pygame.display.set_caption(config.GAME_TITLE)
clock = pygame.time.Clock()
running = True



class EditorTool(Enum):
    NAVIGATE = auto()
    SEEDS = auto()
    REGIONS = auto()

class EditorState:
    def __init__(self):
        self.tool = EditorTool.NAVIGATE

        self.selected_seed_id = None
        self.selected_region_ids = set()



# Initialize camera and world
camera = Camera()
world = World()
renderer = Renderer(world)
editor = EditorState()



# ImGui setup
class UIRenderer(
        ProgrammablePipelineRenderer,
        PygameRenderer
        ):
    pass
imgui.create_context()
ui_renderer = UIRenderer()
io = imgui.get_io()
io.display_size = pygame.display.get_window_size()



def draw_menu_bar(editor, world, renderer):
    if not imgui.begin_main_menu_bar():
        return

    # ----------------------------------------------------------
    # File
    # ----------------------------------------------------------

    if imgui.begin_menu('File', True):
        if imgui.menu_item('New')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Load Seeds...')[0]:
            pass

        if imgui.menu_item('Save Seeds...')[0]:
            pass

        if imgui.menu_item('Load Regions...')[0]:
            pass

        if imgui.menu_item('Save Regions...')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Quit')[0]:
            pass

        imgui.end_menu()

    # ----------------------------------------------------------
    # Edit
    # ----------------------------------------------------------

    if imgui.begin_menu('Edit', True):
        if imgui.menu_item('Undo')[0]:
            pass

        if imgui.menu_item('Redo')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Delete Selected')[0]:
            pass

        if imgui.menu_item('Clear Selection')[0]:
            editor.selected_seed_id = None
            editor.selected_region_ids.clear()

        imgui.end_menu()

    # ----------------------------------------------------------
    # Tool
    # ----------------------------------------------------------

    if imgui.begin_menu('Tool', True):
        clicked, _ = imgui.menu_item(
            'Navigate',
            '',
            editor.tool == EditorTool.NAVIGATE,
        )
        if clicked:
            editor.tool = EditorTool.NAVIGATE

        clicked, _ = imgui.menu_item(
            'Seeds',
            '',
            editor.tool == EditorTool.SEEDS,
        )
        if clicked:
            editor.tool = EditorTool.SEEDS

        clicked, _ = imgui.menu_item(
            'Regions',
            '',
            editor.tool == EditorTool.REGIONS,
        )
        if clicked:
            editor.tool = EditorTool.REGIONS

        imgui.end_menu()

    # ----------------------------------------------------------
    # Seeds
    # ----------------------------------------------------------

    if imgui.begin_menu('Seeds', True):
        if imgui.menu_item('Scatter...')[0]:
            pass

        if imgui.menu_item('Lloyd Relax...')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Clear Seeds')[0]:
            pass

        imgui.end_menu()

    # ----------------------------------------------------------
    # Borders
    # ----------------------------------------------------------

    if imgui.begin_menu('Borders', True):
        if imgui.menu_item('Generate')[0]:
            pass

        if imgui.menu_item('Reroll Unfrozen')[0]:
            pass

        if imgui.menu_item('Reroll Selected')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Clear Generated Borders')[0]:
            pass

        imgui.end_menu()

    # ----------------------------------------------------------
    # Regions
    # ----------------------------------------------------------

    if imgui.begin_menu('Regions', True):
        if imgui.menu_item('Freeze Selected')[0]:
            pass

        if imgui.menu_item('Unfreeze Selected')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Freeze All')[0]:
            pass

        if imgui.menu_item('Unfreeze All')[0]:
            pass

        imgui.end_menu()

    # ----------------------------------------------------------
    # View
    # ----------------------------------------------------------

    if imgui.begin_menu('View', True):
        _, renderer.show_land = imgui.menu_item(
            'Land',
            '',
            renderer.show_land,
        )

        _, renderer.show_lakes = imgui.menu_item(
            'Lakes',
            '',
            renderer.show_lakes,
        )

        _, renderer.show_rivers = imgui.menu_item(
            'Rivers',
            '',
            renderer.show_rivers,
        )

        _, renderer.show_admin_borders = imgui.menu_item(
            'Administrative Borders',
            '',
            renderer.show_admin_borders,
        )

        _, renderer.show_coastlines = imgui.menu_item(
            'Coastlines',
            '',
            renderer.show_coastlines,
        )

        _, renderer.show_cities = imgui.menu_item(
            'Cities',
            '',
            renderer.show_cities,
        )

        imgui.separator()

        _, renderer.show_voronoi_seeds = imgui.menu_item(
            'Voronoi Seeds',
            '',
            renderer.show_voronoi_seeds,
        )

        _, renderer.show_voronoi_edges = imgui.menu_item(
            'Voronoi Edges',
            '',
            renderer.show_voronoi_edges,
        )

        _, renderer.show_generated_borders = imgui.menu_item(
            'Generated Borders',
            '',
            renderer.show_generated_borders,
        )

        _, renderer.show_regions = imgui.menu_item(
            'Region Fill',
            '',
            renderer.show_regions,
        )

        imgui.end_menu()

    imgui.end_main_menu_bar()

    '''
    ui_renderer.process_inputs()
    imgui.new_frame()
    if imgui.begin_main_menu_bar():
        if imgui.begin_menu('View', True):
            _, renderer.show_lakes = imgui.menu_item(
                    'Lakes', '', renderer.show_lakes, True
                    )
            _, renderer.show_rivers = imgui.menu_item(
                    'Rivers', '', renderer.show_rivers, True
                    )
            _, renderer.show_borders = imgui.menu_item(
                    'Borders', '', renderer.show_borders, True
                    )
            #_, renderer.show_land = imgui.menu_item(
            #        'Land', '', renderer.show_land, True
            #        )
            _, renderer.show_coastlines = imgui.menu_item(
                    'Coastlines', '', renderer.show_coastlines, True
                    )
            #_, renderer.show_ocean = imgui.menu_item(
            #        'Ocean', '', renderer.show_ocean, True
            #        )
            _, renderer.show_voronoi = imgui.menu_item(
                    'Voronoi', '', renderer.show_voronoi, True
                    )
            _, renderer.show_cities = imgui.menu_item(
                    'Cities', '', renderer.show_cities, True
                    )
            imgui.end_menu()
        imgui.end_main_menu_bar()
    '''



# Game loop
while running:
    # Get window size
    width, height = pygame.display.get_window_size()

    # Handle camera movement
    dt = clock.tick(60) / 1000.0
    camera.update(dt, width, height)

    # Handle events
    mouse = pygame.mouse.get_pos()
    mouse_pos = camera.screen_to_sphere(*mouse, width, height)
    world.hovered_region = world.region_at(mouse_pos)
    for event in pygame.event.get():
        # Pass the event to ImGui
        ui_renderer.process_event(event)

        # This occurs if the user clicks X to close the window.
        if event.type == pygame.QUIT:
            running = False

        # Place Voronoi points
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                point = camera.screen_to_sphere(*event.pos, width, height)

                if point is not None:
                    world.add_voronoi_seed(point)
                    renderer.update_voronoi(world)

            elif event.button == 3:
                # TODO: remove seed
                pass

    # Handle the menu bar
    #draw_menu_bar(renderer, ui_renderer)
    ui_renderer.process_inputs()
    imgui.new_frame()
    draw_menu_bar(editor, world, renderer)

    # Render the world
    renderer.render(camera, width, height)

    # Render the top menu on top of the world
    imgui.render()
    ui_renderer.render(imgui.get_draw_data())

    # Flip the double buffer
    pygame.display.flip()

ui_renderer.shutdown()
pygame.quit()
