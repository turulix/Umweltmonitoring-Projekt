import datetime
import os
import pickle
from time import sleep

import dotenv
import numpy as np
import pandas as pd
import sqlalchemy
import tensorflow as tf
from keras import Sequential, Input
from keras.src.callbacks import EarlyStopping
from keras.src.layers import LSTM, Dense, Bidirectional
from sqlalchemy import select, text

from data_types.tables import Sensor

dotenv.load_dotenv()

client = sqlalchemy.create_engine(os.environ.get("DATABASE_URL"))

print(tf.config.list_physical_devices('GPU'))


def make_sequence(data, sequence_length, prediction_length=97):
    x, y = [], []
    for i in range(len(data) - sequence_length - prediction_length):
        # Append the sequence of data. And add time of date from index to data
        x.append(data[i:i + sequence_length])
        # Append the value that we want to predict.
        y.append(data[i + sequence_length:i + sequence_length + prediction_length]["value"])

    x, y = np.array(x), np.array(y)
    x = x.reshape((x.shape[0], x.shape[1], x.shape[2]))
    return x, y


def upsert_prediction(engine, timestamp, sensor_id, box_id, value):
    sql = text("""
        INSERT INTO predictions (TimeStamp, Sensor_ID, box_id, value)
        VALUES (:timestamp, :sensor_id, :box_id, :value)
        ON CONFLICT (TimeStamp, Sensor_ID, box_id) DO UPDATE SET
        value = EXCLUDED.value;
    """)
    with engine.connect() as conn:
        #  Parameter als Dictionary zu übergeben
        conn.execute(sql, {'timestamp': timestamp, 'sensor_id': sensor_id, 'box_id': box_id, 'value': float(value)})
        conn.commit()


def main():
    model_cache = {}
    for file in os.listdir("./models"):
        parts = file.split("_")
        box_id = parts[0]
        sensor_id = parts[1]
        timestamp = parts[2]

        model_cache[(box_id, sensor_id)] = {
            "model_path": f"./models/{file}",
            "timestamp": datetime.datetime.fromtimestamp(int(timestamp))
        }

    while True:
        # Get all sensors from database.
        with client.connect() as conn:
            all_sensors = conn.execute(
                select(Sensor.id, Sensor.box_id)
            ).all()

        print(all_sensors)

        for sensor_id, box_id in all_sensors:
            print(f"Processing sensor {sensor_id} on box {box_id}")

            # Get the data for this sensor for the last 1 year.

            date_offset = pd.Timestamp.now() - pd.DateOffset(years=1)

            sql = text("""
                    SELECT date_bin('15 minute', timestamp, TIMESTAMP '2001-01-01') as time, avg(value)
                    FROM data
                    WHERE sensor_id = :sensor_id AND box_id = :box_id AND timestamp > :date_offset
                    GROUP BY time
                    ORDER BY time;
                """)

            with client.connect() as conn:
                data = conn.execute(sql, {'sensor_id': sensor_id, 'box_id': box_id, 'date_offset': date_offset}).all()

            # Skip Processing if there is less than 30 days of data.
            if len(data) < 97 * 30:
                print("Not enough data for LSTM model.")
                continue

            # If there is no data within the last 6h, skip processing.
            last_timestamp = data[-1][0]
            if last_timestamp < pd.Timestamp.now() - pd.Timedelta(hours=6):
                print("No recent data.")
                continue

            df = pd.DataFrame(data, columns=['timestamp', 'value'])
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)

            # Infill data for missing timestamps.
            df = df.resample('15min').mean()

            # If there are more than 20% missing values, skip processing.
            if df['value'].isna().sum() / len(df) > 0.2:
                print(f"Too many missing values. {df['value'].isna().sum() / len(df) * 100}% missing.")
                continue

            df["time_of_day"] = df.index.time
            df["time_of_day"] = df["time_of_day"].apply(lambda x: x.hour * 60 + x.minute)
            df["time_of_day"] = df["time_of_day"] / (24 * 60)

            df["day_of_week"] = df.index.dayofweek / 7
            df["day_of_month"] = df.index.day / 31
            df["month_of_year"] = df.index.month / 12

            train = df.interpolate(method='linear')

            # This is the last 7 days of data.
            # We are using 15-minute intervals, a single day has 96 intervals.
            # So 7 days have 96 * 7 intervals.
            sequence_length = 97 * 7
            prediction_length = 97

            should_train = True
            if (box_id, sensor_id) in model_cache:
                if datetime.datetime.now() - model_cache[(box_id, sensor_id)]["timestamp"] < datetime.timedelta(days=7):
                    should_train = False
                    print(f"Model for {box_id} {sensor_id} is up to date.")
                else:
                    print(f"Model for {box_id} {sensor_id} is older than 1 day. Retraining.")
                    os.remove(model_cache[(box_id, sensor_id)]["model_path"])
                    del model_cache[(box_id, sensor_id)]

            if should_train:
                print("Training model.")
                # Train the model.
                x_train, y_train = make_sequence(train, sequence_length, prediction_length)

                # Build LSTM model.
                model = Sequential()
                model.add(Input(shape=(sequence_length, train.shape[1])))
                model.add(Bidirectional(LSTM(128, return_sequences=True)))
                model.add(Bidirectional(LSTM(128)))
                model.add(Dense(prediction_length))
                model.compile(optimizer='adam', loss='mse', metrics=['mae'])

                print(model.summary())

                early_stopping = EarlyStopping(
                    monitor='val_loss',
                    patience=3,
                    mode="min",
                )

                model.fit(
                    x_train,
                    y_train,
                    epochs=20,
                    batch_size=512,
                    callbacks=[early_stopping],
                    validation_split=0.2,
                    validation_freq=1
                )

                utc_timestamp = int(datetime.datetime.utcnow().timestamp())
                model_path = f"./models/{box_id}_{sensor_id}_{utc_timestamp}_model.pkl"

                with open(model_path, 'wb') as file:
                    pickle.dump(model, file)
                model_cache[(box_id, sensor_id)] = {"model_path": model_path, "timestamp": datetime.datetime.now()}
                print(f"Finished Training of {box_id} {sensor_id}.")
            else:
                model: Sequential = pickle.load(open(model_cache[(box_id, sensor_id)]["model_path"], 'rb'))

            # Test Model against test data.

            # Predict the next 24h.
            data_for_prediction = train.iloc[-sequence_length:]

            # Reshape the data.
            arr = np.array(data_for_prediction)
            arr = arr.reshape((1, arr.shape[0], arr.shape[1]))

            # Predict the next value.
            forecast = model.predict(arr)
            print(f"Forecast: {forecast}")
            if not os.environ.get("USE_TEST") == "true":
                for i, value in enumerate(forecast[0]):
                    timestamp = data_for_prediction.index[-1] + pd.Timedelta(minutes=15 * (i + 1))
                    upsert_prediction(client, timestamp, sensor_id, box_id, value)

        print("Sleeping for 15 minutes.")
        sleep(900)


if __name__ == '__main__':
    main()
