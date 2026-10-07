import pygame

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



# Initialize camera and world
camera = Camera()
world = World()
renderer = Renderer(world)



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
                    #renderer.update_regions(world)

            elif event.button == 3:
                # TODO: remove seed
                pass

    # Handle the menu bar
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



    # Render the world
    renderer.render(camera, width, height)



    # Render the top menu on top of the world
    imgui.render()
    ui_renderer.render(imgui.get_draw_data())

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

ui_renderer.shutdown()
pygame.quit()
