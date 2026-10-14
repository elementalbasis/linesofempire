"""JSON persistence for Voronoi generators; never serializes derived geometry."""
import json
import math
from pathlib import Path

FORMAT = 'linesofempire.voronoi-seeds'
VERSION = 1


def _document(seeds):
    return {
        'format': FORMAT,
        'version': VERSION,
        'coordinates': 'lon-lat-degrees',
        'seeds': [{'lon': lon, 'lat': lat} for lon, lat in seeds],
    }


def _save(seeds, filename):
    path = Path(filename).expanduser()
    if not path.name or path.is_dir():
        raise ValueError('Enter a valid output file path.')
    # Never overwrite existing exports without an explicit overwrite mechanism.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(_document(seeds), stream, indent=2, allow_nan=False)
        stream.write('\n')
    return path


def export_all_seeds(voronoi, filename):
    return _save(voronoi.seeds, filename)


def export_selected_seeds(voronoi, selected_ids, filename):
    indices = sorted(selected_ids)
    if not indices:
        raise ValueError('No Voronoi regions are selected.')
    if any(type(i) is not int or i < 0 or i >= len(voronoi.seeds) for i in indices):
        raise ValueError('Selection contains an invalid Voronoi region ID.')
    return _save([voronoi.seeds[i] for i in indices], filename)


def load_seeds(filename):
    path = Path(filename).expanduser()
    with path.open(encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise ValueError('Not a Lines of Empire seed file.')
    if data.get('version') != VERSION or data.get('coordinates') != 'lon-lat-degrees':
        raise ValueError('Unsupported seed file version or coordinate system.')
    records = data.get('seeds')
    if not isinstance(records, list):
        raise ValueError('Seed list is missing or invalid.')
    seeds = []
    for record in records:
        if not isinstance(record, dict) or 'lon' not in record or 'lat' not in record:
            raise ValueError('Malformed seed coordinates.')
        lon, lat = record['lon'], record['lat']
        if (type(lon) not in (int, float) or type(lat) not in (int, float)
                or not math.isfinite(lon) or not math.isfinite(lat)
                or not -180 <= lon <= 180 or not -90 <= lat <= 90):
            raise ValueError('Seed coordinates must be finite longitude/latitude in degrees.')
        seeds.append((float(lon), float(lat)))
    return seeds
