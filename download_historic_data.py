import os
from datetime import datetime, timedelta, timezone

import dotenv
import requests
import sqlalchemy
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from data_types.tables import Base, Box, Sensor, Data

dotenv.load_dotenv()

client = sqlalchemy.create_engine(os.environ.get("DATABASE_URL"))
Base.metadata.create_all(client)
session = sessionmaker(bind=client)()

station_ids = [
    "5a414a7cfaf306000fbb6b99",  # (Wittenau)
    "649d78a83efed3000865aa6b",  # (NTT-HO_PB)
    "6407415c7bd0650008bc445a",  # (Gartenarbeitsschule Lichtenberg)

    "65e8d93acbf5700007f920ca",  # (Leipziger Straße)
    "5a8c3d36bc2d4100190c49fb",  # (Osloer Straße)
    "5d9ef41e25683a001ad916c3",  # (Frankfurter Allee/Proskauer Straße)
    "5bf93ceba8af82001afc4c32",  # (Tempelhofer Damm)
    "5984c712e3b1fa0010691509",  # (Karl-Marx-Straße)
]

for station_id in station_ids:
    station_details = requests.get(f"https://api.opensensemap.org/boxes/{station_id}").json()
    try:
        session.add(Box(
            id=station_id,
            model=station_details["model"],
            name=station_details["name"],
            location=from_shape(Point([station_details["currentLocation"]["coordinates"][0],
                                       station_details["currentLocation"]["coordinates"][1]]), srid=4326),
            exposure=station_details["exposure"]
        ))

        session.commit()
    except IntegrityError as e:
        print(f"Box '{station_id}' already in database. Skipping.")
        session.rollback()

    for sensor in station_details["sensors"]:
        sensor_id = sensor["_id"]
        title = sensor["title"]
        try:
            session.add(Sensor(
                id=sensor_id,
                box_id=station_id,
                icon=sensor["icon"],
                title=title,
                unit=sensor["unit"],
                sensor_type=sensor["sensorType"]
            ))

            session.commit()
        except IntegrityError as e:
            print(f"Sensor '{sensor_id}' on box '{station_id}' already exists in db. Skipping creation. ")
            session.rollback()

        # Get the last two years of measurements for each sensor in 48 hour intervals
        now = datetime.now()
        for i in tqdm(range(1, 730)):
            delta = timedelta(days=1)
            measurements_req = requests.get(
                f"https://api.opensensemap.org/boxes/{station_id}/data/{sensor_id}",
                {
                    "from-date": (now - delta * i).isoformat('T') + "Z",
                    "to-date": (now - delta * (i - 1)).isoformat('T') + "Z"
                }
            ).json()

            processed_data = []
            unique_datapoints = set()
            for measurement in measurements_req:
                # '2024-06-20T10:04:48.775Z'
                # This is because at some point the API started returning measurements with the same timestamp.
                # This is a workaround to avoid inserting duplicate measurements.
                timestamp = datetime.strptime(measurement["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=timezone.utc)

                if (station_id, sensor_id, timestamp) in unique_datapoints:
                    continue
                unique_datapoints.add((station_id, sensor_id, timestamp))

                processed_data.append({
                    "box_id": station_id,
                    "sensor_id": sensor_id,
                    "timestamp": timestamp,
                    "value": float(measurement["value"])
                })

            try:
                if len(processed_data) == 0:
                    continue
                smts = insert(Data).values(processed_data)
                smts = smts.on_conflict_do_update(
                    index_elements=[Data.box_id, Data.sensor_id, Data.timestamp],
                    set_={
                        "value": smts.excluded.value
                    }
                )
                session.execute(smts)
                session.commit()
            except Exception as e:
                print(e)
                session.rollback()
