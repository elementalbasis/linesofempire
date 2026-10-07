import math

import cartopy.io.shapereader as shpreader
import numpy as np
import pandas as pd


# Cities closer than this are considered to overlap.
COLLAPSE_DISTANCE_DEGREES = 1.5

# Higher number = more important symbol.
SYMBOL_RANK = {
    'circle': 1,
    'circle+dot': 2,
    'circle+star': 3,
}


def angular_distance_matrix(a, b):
    """Return pairwise angular separations in degrees using lat/lon directly."""
    lat1 = np.radians(a['Lat'].to_numpy())[:, None]
    lon1 = np.radians(a['Lon'].to_numpy())[:, None]
    lat2 = np.radians(b['Lat'].to_numpy())[None, :]
    lon2 = np.radians(b['Lon'].to_numpy())[None, :]

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    )
    h = np.clip(h, 0.0, 1.0)

    return np.degrees(2.0 * np.arcsin(np.sqrt(h)))


def average_longitude(longitudes):
    """Average nearby longitudes without breaking at the +/-180 degree seam."""
    longitudes = np.asarray(longitudes, dtype=float)
    reference = longitudes[0]
    offsets = (longitudes - reference + 180.0) % 360.0 - 180.0
    mean = reference + offsets.mean()
    return (mean + 180.0) % 360.0 - 180.0


def merge_equal_rank(group):
    """Merge an equal-rank group at its average lat/lon position."""
    row = group.iloc[0].copy()
    row['Name'] = '/'.join(group['Name'])
    row['Lat'] = group['Lat'].mean()
    row['Lon'] = average_longitude(group['Lon'])
    return row


def cluster_equal_rank(df, max_distance):
    """Merge connected same-rank cities whose separation is <= max_distance."""
    if len(df) <= 1:
        return df.copy().reset_index(drop=True)

    distances = angular_distance_matrix(df, df)
    adjacent = distances <= max_distance

    visited = np.zeros(len(df), dtype=bool)
    merged = []

    for start in range(len(df)):
        if visited[start]:
            continue

        stack = [start]
        visited[start] = True
        component = []

        while stack:
            i = stack.pop()
            component.append(i)

            neighbors = np.flatnonzero(adjacent[i] & ~visited)
            for j in neighbors:
                visited[j] = True
                stack.append(j)

        merged.append(merge_equal_rank(df.iloc[component]))

    return pd.DataFrame(merged).reset_index(drop=True)


def collapse_cities(df, max_distance):
    """
    Collapse overlapping city symbols.

    Higher-rank cities suppress lower-rank cities. Equal-rank cities are
    clustered and replaced by one city at their average position.
    """
    survivors = pd.DataFrame(columns=df.columns)

    for rank in sorted(SYMBOL_RANK.values(), reverse=True):
        symbol = next(symbol for symbol, value in SYMBOL_RANK.items() if value == rank)
        current = df[df['Symbol'] == symbol].copy().reset_index(drop=True)

        if current.empty:
            continue

        # Higher-ranked cities always win. Remove current-rank cities that are
        # already too close to a higher-ranked survivor.
        if not survivors.empty:
            distances = angular_distance_matrix(current, survivors)
            keep = ~np.any(distances <= max_distance, axis=1)
            current = current[keep].reset_index(drop=True)

        if current.empty:
            continue

        # Equal-ranked cities merge with one another.
        current = cluster_equal_rank(current, max_distance)

        survivors = pd.concat(
            [survivors, current],
            ignore_index=True,
        )

    return survivors.reset_index(drop=True)


filename = shpreader.natural_earth(
    resolution='10m',
    category='cultural',
    name='populated_places',
)
reader = shpreader.Reader(filename)

cities = []

for record in reader.records():
    name = record.attributes['NAME']
    scalerank = record.attributes['SCALERANK']
    featurecla = record.attributes['FEATURECLA']
    lon = record.attributes['LONGITUDE']
    lat = record.attributes['LATITUDE']

    if scalerank <= 1:
        if featurecla == 'Admin-0 capital':
            symbol = 'circle+star'
        else:
            symbol = 'circle+dot'
    elif scalerank == 2:
        if featurecla == 'Admin-0 capital':
            symbol = 'circle+dot'
        else:
            symbol = 'circle'
    elif scalerank == 3:
        if featurecla == 'Admin-0 capital':
            symbol = 'circle'
        else:
            symbol = 'circle'
    elif scalerank == 4:
        symbol = 'circle'
    else:
        symbol = 'none'



    overrides = {
            #Promote
            'Brasília': 'circle+star',
            'Ankara': 'circle+star',
            'Kyoto': 'circle+dot',
            'Milan': 'circle+dot',
            'Barcelona': 'circle+dot',
            'Karachi': 'circle+dot',
            'Ho Chi Minh City': 'circle+dot',
            'Hamburg': 'circle+dot',

            #Demote
            'Kabul': 'circle+dot',
            'Johannesburg': 'circle+dot',
            #'Madrid': 'circle+dot',
            #'Stockholm': 'circle+dot',
            #'Amsterdam': 'circle+dot',
            #'Athens': 'circle+dot',
            }

    if name in overrides:
        symbol = overrides[name]


    if symbol is not None:
        cities.append({
            'Name': name,
            'Symbol': symbol,
            'Lat': lat,
            'Lon': lon,
        })

cities = pd.DataFrame(cities)
cities = collapse_cities(cities, COLLAPSE_DISTANCE_DEGREES)

print(cities.to_csv(sep='\t', index=False), end='')
