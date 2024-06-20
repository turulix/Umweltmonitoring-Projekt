import sqlalchemy
import os
from datetime import datetime, timedelta, timezone
import json
import requests
from tqdm import tqdm
import dotenv
import pandas as pd

dotenv.load_dotenv()

client = sqlalchemy.create_engine(os.environ.get("DATABASE_URL"))

station_ids = [
    "65e8d93acbf5700007f920ca",  # (Leipziger Straße)
    "5a8c3d36bc2d4100190c49fb",  # (Osloer Straße)
    "5d9ef41e25683a001ad916c3",  # (Frankfurter Allee/Proskauer Straße)
    "5bf93ceba8af82001afc4c32",  # (Tempelhofer Damm)
    "5984c712e3b1fa0010691509"  # (Karl-Marx-Straße)
]
with client.connect() as conn:
    for station_id in station_ids:
        station_details = requests.get(f"https://api.opensensemap.org/boxes/{station_id}").json()
        station_df = pd.DataFrame.from_dict(station_details, orient="index").T[
            ["_id", "model", "name", "currentLocation", "exposure"]]
        # Convert the currentLocation to a geopandas POINT
        station_df["currentLocation"] = station_df["currentLocation"].apply(
            lambda x: f"POINT ({x['coordinates'][0]} {x['coordinates'][1]})")
        station_df = station_df.rename(columns={"_id": "id", "currentLocation": "location"}).T.T
        station_df.to_sql("boxes", conn, if_exists="append", index=False)
        for sensor in station_details["sensors"]:
            sensor_id = sensor["_id"]
            title = sensor["title"]
            # Get the last two years of measurements for each sensor in 48 hour intervals
            now = datetime.now()
            sensor_data = []
            for i in tqdm(range(1, 730)):
                delta = timedelta(days=1)
                measurements_req = requests.get(
                    f"https://api.opensensemap.org/boxes/{station_id}/data/{sensor_id}?"
                    f"from-date={(now - delta * i).isoformat('T')}Z&to-date={(now - delta * (i - 1)).isoformat('T')}Z").json()
                sensor_data.extend(measurements_req)
                if len(measurements_req) == 0:
                    # No more data available, we can terminate early
                    break
            # Store Sensor Data To File
            with open(f"{station_id}_{title}.json", "w") as f:
                f.write(str(json.dumps(sensor_data, indent=4)))
