"""Editor tools, active geometry layer, selection, and mouse interaction.

Does not depend on ImGui or the renderer implementation.
"""
from enum import Enum, auto
import math

import numpy as np
import pygame

import config


class EditorTool(Enum):
    NAVIGATE = auto()
    SELECT = auto()
    EDIT = auto()


class EditorLayer(Enum):
    VORONOI = auto()
    ATOMS = auto()
    REGIONS = auto()


class EditorState:
    def __init__(self):
        self.tool = EditorTool.NAVIGATE
        self.layer = EditorLayer.VORONOI
        self.selected = {layer: set() for layer in EditorLayer}
        self.hovered = {layer: None for layer in EditorLayer}
        self.selection_start = None
        self.selection_end = None
        self.dragging_seed_id = None
        self.dragging_seed_point = None

    @property
    def selection(self):
        return self.selected[self.layer]

    @property
    def selection_rectangle(self):
        if self.selection_start is None or self.selection_end is None:
            return None
        x1, y1 = self.selection_start
        x2, y2 = self.selection_end
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def clear_selection(self):
        self.selection.clear()

    def select_all(self, world):
        if self.layer == EditorLayer.VORONOI:
            self.selection.update(range(len(world.voronoi.region_indices)))

    def cancel_rectangle(self):
        self.selection_start = None
        self.selection_end = None

    def cancel_drag(self, renderer):
        self.dragging_seed_id = None
        self.dragging_seed_point = None
        renderer.clear_seed_preview()

    def remap_after_seed_deletion(self, index):
        selected = self.selected[EditorLayer.VORONOI]
        self.selected[EditorLayer.VORONOI] = {
            old if old < index else old - 1
            for old in selected if old != index
        }
        self.hovered[EditorLayer.VORONOI] = None

    def update_hover(self, mouse, world, camera, width, height, capture_mouse):
        self.hovered[EditorLayer.VORONOI] = None
        if (self.tool == EditorTool.SELECT and self.layer == EditorLayer.VORONOI
                and not capture_mouse and self.selection_start is None):
            point = camera.screen_to_sphere(*mouse, width, height)
            self.hovered[EditorLayer.VORONOI] = world.voronoi.region_at(point)

        # The old final-region hover must not obscure Voronoi selection.
        if self.layer == EditorLayer.REGIONS and world.partition.atoms and not capture_mouse:
            point = camera.screen_to_sphere(*mouse, width, height)
            world.hovered_region = world.partition.region_at(point)
        else:
            world.hovered_region = None

    def handle_event(self, event, world, camera, renderer, width, height,
                     capture_mouse=False, capture_keyboard=False):
        if event.type == pygame.WINDOWFOCUSLOST:
            self.cancel_rectangle()
            self.cancel_drag(renderer)
            return

        if event.type == pygame.KEYDOWN and not capture_keyboard:
            if event.key == pygame.K_ESCAPE:
                if self.selection_start is not None:
                    self.cancel_rectangle()
                elif self.dragging_seed_id is not None:
                    self.cancel_drag(renderer)
                else:
                    self.clear_selection()
            elif event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                self.select_all(world)

        if self.tool == EditorTool.SELECT and self.layer == EditorLayer.VORONOI:
            self._selection_event(event, world, camera, width, height, capture_mouse)
        elif self.tool == EditorTool.EDIT and self.layer == EditorLayer.VORONOI:
            self._seed_event(event, world, camera, renderer, width, height, capture_mouse)

    def _selection_event(self, event, world, camera, width, height, capture_mouse):
        voronoi = world.voronoi
        if event.type == pygame.MOUSEBUTTONDOWN:
            if capture_mouse:
                return
            if event.button == 1:
                self.selection_start = event.pos
                self.selection_end = event.pos
            elif event.button == 3:
                point = camera.screen_to_sphere(*event.pos, width, height)
                region_id = voronoi.region_at(point)
                if region_id is not None:
                    self.selection.discard(region_id)
        elif event.type == pygame.MOUSEMOTION and self.selection_start is not None:
            self.selection_end = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.selection_start is None:
                return
            self.selection_end = event.pos
            rect = self.selection_rectangle
            x1, y1, x2, y2 = rect
            if math.hypot(x2-x1, y2-y1) < config.SELECTION_DRAG_THRESHOLD:
                point = camera.screen_to_sphere(*event.pos, width, height)
                region_id = voronoi.region_at(point)
                chosen = set() if region_id is None else {region_id}
            else:
                chosen = voronoi.regions_in_rectangle(rect, camera, width, height)
            if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                self.selection.clear()
            self.selection.update(chosen)
            self.cancel_rectangle()

    def _seed_event(self, event, world, camera, renderer, width, height, capture_mouse):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if capture_mouse or event.button not in (1, 3):
                return
            point = camera.screen_to_sphere(*event.pos, width, height)
            if point is None:
                return
            radius = math.asin(min(1.0, config.VORONOI_SEED_PICK_RADIUS / camera.zoom))
            seed_id = world.voronoi.nearest_seed(point, radius)
            if event.button == 1:
                if seed_id is not None:
                    self.dragging_seed_id = seed_id
                    self.dragging_seed_point = point
                else:
                    world.add_voronoi_seed(point)
                    self._refresh_geometry(world, renderer)
            elif seed_id is not None:
                world.remove_voronoi_seed(seed_id)
                self.remap_after_seed_deletion(seed_id)
                if not world.voronoi.region_indices:
                    self.selected[EditorLayer.VORONOI].clear()
                self._refresh_geometry(world, renderer)
        elif event.type == pygame.MOUSEMOTION and self.dragging_seed_id is not None:
            point = camera.screen_to_sphere(*event.pos, width, height)
            if point is not None:
                boundary = world.voronoi.preview_region(self.dragging_seed_id, point)
                # Do not commit a position for which the preview is invalid.
                if len(boundary) >= 3:
                    self.dragging_seed_point = point
                    renderer.update_seed_preview(point, boundary)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_seed_id is None:
                return
            index, point = self.dragging_seed_id, self.dragging_seed_point
            self.cancel_drag(renderer)
            if point is not None:
                old = world.voronoi.seed_vertices[index]
                if not np.allclose(old, point, rtol=0, atol=config.VORONOI_MOVE_TOLERANCE):
                    world.move_voronoi_seed(index, point)
                    self._refresh_geometry(world, renderer)

    @staticmethod
    def _refresh_geometry(world, renderer):
        renderer.update_voronoi(world)
        renderer.update_generated_borders(world)
        renderer.update_atoms(world)
        renderer.update_regions(world)
