import pandas as pd

df = pd.read_csv('cities.tsv', sep = '\t')

for index, row in df.iterrows():
    lon = row['Lon']
    lat = row['Lat']
    name = row['Name']
    symbol = row['Symbol']
