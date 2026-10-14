import imgui

import config
from editor import EditorTool, EditorLayer
from seed_io import export_all_seeds, export_selected_seeds, load_seeds


class SeedFileDialog:
    """Single save/load modal; saving favors the current Voronoi selection."""

    def __init__(self):
        self.action = None
        self.pending = False
        self.filename = config.SEED_FILE_DEFAULT
        self.error = ''

    def request(self, action):
        self.action = action
        self.pending = True
        self.filename = config.SEED_FILE_DEFAULT
        self.error = ''

    def draw(self, editor, world, renderer):
        if self.action is None:
            return

        title = 'Load Seeds' if self.action == 'load' else 'Save Seeds'
        if self.pending:
            imgui.open_popup(title)
            self.pending = False

        opened, _ = imgui.begin_popup_modal(title)
        if not opened:
            return

        _, self.filename = imgui.input_text(
            'Path', self.filename, config.SEED_FILE_PATH_MAX_LENGTH
        )

        if self.action == 'save':
            selected = editor.selected[EditorLayer.VORONOI]
            count = len(selected) if selected else len(world.voronoi.seeds)
            scope = 'selected' if selected else 'all'
            imgui.text(f'Saving {count} {scope} Voronoi seeds')
        else:
            imgui.text('Loading replaces all current Voronoi seeds.')

        if imgui.button('Load' if self.action == 'load' else 'Save'):
            try:
                if self.action == 'load':
                    seeds = load_seeds(self.filename)
                    world.replace_voronoi_seeds(seeds)
                    editor.cancel_drag(renderer)
                    editor.cancel_rectangle()
                    editor.selected[EditorLayer.VORONOI].clear()
                    editor.hovered[EditorLayer.VORONOI] = None
                    editor._refresh_geometry(world, renderer)
                else:
                    selected = editor.selected[EditorLayer.VORONOI]
                    if selected:
                        export_selected_seeds(world.voronoi, selected, self.filename)
                    else:
                        export_all_seeds(world.voronoi, self.filename)
            except (OSError, ValueError, TypeError) as exc:
                self.error = str(exc)
            else:
                imgui.close_current_popup()
                self.action = None

        imgui.same_line()
        if imgui.button('Cancel'):
            imgui.close_current_popup()
            self.action = None

        if self.error:
            imgui.text_colored(self.error, 1.0, 0.35, 0.35)

        imgui.end_popup()


_seed_file_dialog = SeedFileDialog()


def draw_file_dialogs(editor, world, renderer):
    """Call every frame, outside the menu-bar scope."""
    _seed_file_dialog.draw(editor, world, renderer)


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
            _seed_file_dialog.request('load')

        if imgui.menu_item('Save Seeds...')[0]:
            _seed_file_dialog.request('save')

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

        if imgui.menu_item('Select All')[0]:
            editor.select_all(world)

        if imgui.menu_item('Clear Selection')[0]:
            editor.clear_selection()

        imgui.end_menu()

    # ----------------------------------------------------------
    # Tool
    # ----------------------------------------------------------

    if imgui.begin_menu('Tool', True):
        for tool in EditorTool:
            clicked, _ = imgui.menu_item(
                    tool.name.title(),
                    '',
                    editor.tool == tool,
                    )
            if clicked:
                editor.tool = tool

        imgui.end_menu()

    # ----------------------------------------------------------
    # Layer
    # ----------------------------------------------------------

    if imgui.begin_menu('Layer', True):
        for layer in EditorLayer:
            clicked, _ = imgui.menu_item(
                    layer.name.title(),
                    '',
                    editor.layer == layer,
                    )
            if clicked:
                editor.layer = layer

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
            world.generate_borders()
            renderer.update_generated_borders(world)
            renderer.update_atoms(world)
            renderer.update_regions(world)

        if imgui.menu_item('Reroll Unfrozen')[0]:
            world.reroll_borders()
            renderer.update_generated_borders(world)
            renderer.update_atoms(world)
            renderer.update_regions(world)

        if imgui.menu_item('Reroll Selected')[0]:
            pass

        imgui.separator()

        if imgui.menu_item('Clear Generated Borders')[0]:
            world.clear_borders()
            renderer.update_generated_borders(world)
            renderer.update_atoms(world)
            renderer.update_regions(world)

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

        _, renderer.show_georaster = imgui.menu_item(
            'GeoRaster',
            '',
            renderer.show_georaster,
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

        _, renderer.show_atom_edges = imgui.menu_item(
            'Atom Edges',
            '',
            renderer.show_atom_edges,
        )

        _, renderer.show_region_edges = imgui.menu_item(
            'Final Region Edges',
            '',
            renderer.show_region_edges,
        )

        imgui.end_menu()

    imgui.end_main_menu_bar()


def draw_selection_rectangle(editor):
    rect = editor.selection_rectangle

    if rect is None:
        return

    x1, y1, x2, y2 = rect

    draw_list = imgui.get_foreground_draw_list()

    color = config.SELECTION_RECT_COLOR

    fill = imgui.get_color_u32_rgba(
        *color,
        config.SELECTION_RECT_OPACITY,
    )
    border = imgui.get_color_u32_rgba(
        *color,
        1.0,
    )

    draw_list.add_rect_filled(
        x1, y1, x2, y2, fill,
    )

    draw_list.add_rect(
        x1, y1, x2, y2,
        border,
        thickness=config.SELECTION_RECT_THICKNESS,
    )

