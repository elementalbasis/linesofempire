import cartopy.io.shapereader as shpreader
#import pandas as pd

filename = shpreader.natural_earth(
        resolution = '10m',
        category = 'cultural',
        name = 'populated_places',
        )
reader = shpreader.Reader(filename)

#df = pd.DataFrame(record.attributes for record in reader.records())

for record in reader.records():
    name = record.attributes['NAME']
    #population = record.attributes['POP_MAX']
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
        symbol = 'circle+dot'
    elif scalerank == 3:
        if featurecla == 'Admin-0 capital':
            symbol = 'circle+dot'
        else:
            symbol = 'circle'
    elif name == 'Kyoto':
        symbol = 'circle+dot'
    else:
        symbol = None

    '''
    if scalerank <= 1 and featurecla == 'Admin-0 capital':
        symbol = 'circle_star'
    elif scalerank <= 3:
        symbol = 'circle_dot'
    elif scalerank <= 5:
        symbol = 'circle'
    else:
        symbol = None
    '''

    if symbol != None:
        print(name, symbol, lat, lon, sep = '\t')
        #print(name, scalerank, featurecla, sep = '\t')
