"""Pointer-driven globe navigation, independent of the editing layer."""
import pygame


class NavigationController:
    def __init__(self):
        self.anchor = None

    def cancel(self):
        self.anchor = None

    def handle_event(self, event, camera, width, height, tool, capture_mouse):
        # Zoom is available in every editor tool and on every layer.
        if event.type == pygame.MOUSEWHEEL:
            if not capture_mouse:
                camera.zoom_at(pygame.mouse.get_pos(), event.y, width, height)
            return

        # Globe dragging belongs exclusively to Navigate.
        if tool.name != 'NAVIGATE':
            self.cancel()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not capture_mouse:
                self.anchor = camera.screen_to_sphere(*event.pos, width, height)
        elif event.type == pygame.MOUSEMOTION and self.anchor is not None:
            camera.align_point_to_screen(self.anchor, event.pos, width, height)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.cancel()
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.cancel()
