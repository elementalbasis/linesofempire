import pygame

# Parameters
game_title = "Lines of Empire"

# pygame setup
pygame.init()
screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
pygame.display.set_caption(game_title)
clock = pygame.time.Clock()
running = True

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
    screen.fill("purple")

    # RENDER YOUR GAME HERE

    # flip() the display to put your work on screen
    #
    # Even though this function is called flip(), according to the PyGame
    # documentation, it simply updates the screen. The related update()
    # function updates only a selected portion of the screen. Neither of
    # these functions work if using OPENGL.
    pygame.display.flip()

    clock.tick(60) # limits FPS to 60

pygame.quit()
