from datetime import datetime, timedelta, timezone
import json
import requests
from tqdm import tqdm

station_ids = [
    "65e8d93acbf5700007f920ca",  # (Leipziger Straße)
    "5a8c3d36bc2d4100190c49fb",  # (Osloer Straße)
    "5d9ef41e25683a001ad916c3",  # (Frankfurter Allee/Proskauer Straße)
    "5bf93ceba8af82001afc4c32",  # (Tempelhofer Damm)
    "5984c712e3b1fa0010691509"  # (Karl-Marx-Straße)
]

for station_id in station_ids:
    sensors_req = requests.get(f"https://api.opensensemap.org/boxes/{station_id}/sensors").json()
    for sensor in sensors_req["sensors"]:
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
                break
        # Store Sensor Data To File
        with open(f"{station_id}_{title}.json", "w") as f:
            f.write(str(json.dumps(sensor_data, indent=4)))
