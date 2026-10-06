from matplotlib.colors import to_rgb

# Parameters
GAME_TITLE = 'Lines of Empire'

MAP_SCALE = '50m' # Options are: 10m, 50m, 110m, from Natural Earth

INITIAL_LON = 15.0
INITIAL_LAT = 50.0
INITIAL_ZOOM = 300.0

CAMERA_SPEED = 60.0 # degrees per second
ZOOM_SPEED = 1.5
FAST_SPEED_MULTIPLIER = 3.0
SLOW_SPEED_MULTIPLIER = 0.25

MIN_ZOOM_MULTIPLIER = 0.35
MAX_ZOOM_MULTIPLIER = 8

# Map colors and styling
LAND_COLOR = to_rgb('#d8c99b')
OCEAN_COLOR = to_rgb('#557c7a')
COAST_COLOR = to_rgb('#282620')
OUTSIDE_COLOR = to_rgb('#18191b')
BORDER_COLOR = to_rgb('#635441')

COAST_THICKNESS = 2.0
RIVER_THICKNESS = 1.25
BORDER_THICKNESS = 1.0
#PROVINCE_THICKNESS = 0.75
HORIZON_THICKNESS = 2.0

OCEAN_SEGMENTS = 256


GLOBE_VERTEX_SHADER = 'shaders/globe.vert'
HORIZON_GEOMETRY_SHADER = 'shaders/horizon.geom'
DISK_VERTEX_SHADER = 'shaders/disk.vert'
SOLID_FRAGMENT_SHADER = 'shaders/solid.frag'

