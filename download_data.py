import sqlalchemy
import os
from datetime import datetime, timedelta, timezone
import json
import requests
from geoalchemy2.shape import from_shape
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
import dotenv
import pandas as pd
import geopandas as pgd
from shapely.geometry import Point

from data_types.tables import Base, Box, Sensor, Data

dotenv.load_dotenv()

client = sqlalchemy.create_engine(os.environ.get("DATABASE_URL"))
Base.metadata.create_all(client)
session = sessionmaker(bind=client)()

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

        session.add(Box(
            id=station_id,
            model=station_details["model"],
            name=station_details["name"],
            location=from_shape(Point([station_details["currentLocation"]["coordinates"][0],
                                       station_details["currentLocation"]["coordinates"][1]]), srid=4326),
            exposure=station_details["exposure"]
        ))

        session.commit()

        for sensor in station_details["sensors"]:
            sensor_id = sensor["_id"]
            title = sensor["title"]

            session.add(Sensor(
                id=sensor_id,
                box_id=station_id,
                icon=sensor["icon"],
                title=title,
                unit=sensor["unit"],
                sensor_type=sensor["sensorType"]
            ))

            session.commit()

            # Get the last two years of measurements for each sensor in 48 hour intervals
            now = datetime.now()
            sensor_data = []
            for i in tqdm(range(1, 730)):
                delta = timedelta(days=1)
                measurements_req = requests.get(
                    f"https://api.opensensemap.org/boxes/{station_id}/data/{sensor_id}?"
                    f"from-date={(now - delta * i).isoformat('T')}Z&to-date={(now - delta * (i - 1)).isoformat('T')}Z"
                ).json()
                sensor_data.extend(measurements_req)

            # Store Sensor Data To Database
            processed_data = []
            for measurement in sensor_data:
                # '2024-06-20T10:04:48.775Z'
                processed_data.append(Data(
                    box_id=station_id,
                    sensor_id=sensor_id,
                    timestamp=datetime.strptime(measurement["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                        tzinfo=timezone.utc),
                    value=float(measurement["value"])
                ))

            session.add_all(processed_data)
            session.commit()

            # Store Sensor Data To File
            # with open(f"./data/{station_id}_{title}.json", "w") as f:
            #     f.write(str(json.dumps(sensor_data, indent=4)))
