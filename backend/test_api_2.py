import sys
import os
import pandas as pd
import datetime

# Patch system path to import services
sys.path.append(os.path.abspath("."))

from services.ee_service import get_timeseries, get_benchmark_timeseries
import geopandas as gpd

lotes = [
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-63.25, -31.68], [-63.24, -31.68], [-63.24, -31.67], [-63.25, -31.67], [-63.25, -31.68]]]
        },
        "properties": {
            "temp_id": "lote_0",
            "Lote_Name": "Lote 1"
        }
    }
]

gdf_lotes = gpd.GeoDataFrame.from_features(lotes)
gdf_lotes.set_crs(epsg=4326, inplace=True)

start = datetime.date.today() - datetime.timedelta(days=30)
end = datetime.date.today()

print("Calling get_benchmark_timeseries...")
df = get_benchmark_timeseries(gdf_lotes, start, end, "NDVI")

print("DF INDEX:")
print(df.index)

print("\nDF TYPES:")
print(df.dtypes)

print("\nDF VALUES:")
print(df)
