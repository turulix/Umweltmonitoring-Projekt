import os
from datetime import datetime, timezone
from time import sleep

import dotenv
import requests
import sqlalchemy
from sqlalchemy import func, select, Insert
from sqlalchemy.orm import sessionmaker

from data_types.tables import Base, Sensor, Data

dotenv.load_dotenv()
client = sqlalchemy.create_engine(os.environ.get("DATABASE_URL"))
session = sessionmaker(bind=client)()
Base.metadata.create_all(client)
with client.connect() as conn:
    while True:
        # Get all sensors from database.
        all_sensors = conn.execute(
            select(Sensor.id, Sensor.box_id)
        ).all()
        for (sensor_id, box_id) in all_sensors:
            # Get the latest timestamp for this sensor.
            latest_timestamp = conn.execute(
                select(func.max(Data.timestamp))
                .where(Data.sensor_id == sensor_id)
                .where(Data.box_id == box_id)
            ).scalar()
            if latest_timestamp is None:
                print(f"No data for sensor {sensor_id} on box {box_id}. Skipping.")
                continue
            latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)

            # Get the latest data from the sensor.
            latest_data = requests.get(f"https://api.opensensemap.org/boxes/{box_id}/data/{sensor_id}").json()
            for data in latest_data:
                timestamp = datetime.strptime(data["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=timezone.utc)
                if timestamp > latest_timestamp:
                    print(f"New data for sensor {sensor_id} on box {box_id} at {data['createdAt']}: {data['value']}")
                    # Insert the new data into the database.
                    session.add(Data(
                        box_id=box_id,
                        sensor_id=sensor_id,
                        timestamp=timestamp,
                        value=data["value"]
                    ))
                    session.commit()
        sleep(60)
