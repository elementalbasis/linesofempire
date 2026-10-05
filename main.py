import pygame
import moderngl
import cartopy.io.shapereader as shpreader

# Parameters
GAME_TITLE = 'Lines of Empire'
MAP_SCALE = '50m' # Options are: 10m, 50m, 110m

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
    ctx.clear(0, 0, 0, 1)

    # RENDER YOUR GAME HERE

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
