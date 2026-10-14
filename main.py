import pygame
import imgui
from imgui.integrations.pygame import PygameRenderer
from imgui.integrations.opengl import ProgrammablePipelineRenderer

import config
from camera import Camera
from world import World
from renderer import Renderer
from editor import EditorState
from ui import draw_menu_bar, draw_selection_rectangle, draw_file_dialogs


class UIRenderer(ProgrammablePipelineRenderer, PygameRenderer):
    pass


def main():
    pygame.init()
    pygame.display.set_mode(
        (config.INITIAL_SCREEN_WIDTH, config.INITIAL_SCREEN_HEIGHT),
        pygame.RESIZABLE | pygame.OPENGL | pygame.DOUBLEBUF,
    )
    pygame.display.set_caption(config.GAME_TITLE)
    clock = pygame.time.Clock()
    camera = Camera()
    world = World()
    renderer = Renderer(world)
    editor = EditorState()

    imgui.create_context()
    ui_renderer = UIRenderer()
    io = imgui.get_io()
    running = True
    try:
        while running:
            width, height = pygame.display.get_window_size()
            dt = clock.tick(config.TARGET_FPS) / 1000.0
            camera.update(dt, width, height)

            for event in pygame.event.get():
                ui_renderer.process_event(event)
                if event.type == pygame.QUIT:
                    running = False
                editor.handle_event(
                    event, world, camera, renderer, width, height,
                    capture_mouse=io.want_capture_mouse,
                    capture_keyboard=io.want_capture_keyboard,
                )

            ui_renderer.process_inputs()
            io.display_size = width, height
            imgui.new_frame()
            draw_menu_bar(editor, world, renderer)
            draw_file_dialogs(editor, world, renderer)
            editor.update_hover(
                pygame.mouse.get_pos(), world, camera, width, height,
                io.want_capture_mouse,
            )
            draw_selection_rectangle(editor)
            renderer.render(camera, width, height, editor)
            imgui.render()
            ui_renderer.render(imgui.get_draw_data())
            pygame.display.flip()
    finally:
        ui_renderer.shutdown()
        pygame.quit()


if __name__ == '__main__':
    main()
