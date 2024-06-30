# Umweltmonitoring

## Introduction
This project is a simple environmental monitoring system that uses the [OpenSenseMap](https://opensensemap.org/) API to download
and store environmental data. The data is then used to predict future values using a LSTM neural network.

Configured & Hosted Demo: [https://uwm.turulix.de/](https://uwm.turulix.de/)
```
Username: viewer
Password: viewer
```

## Setup

Start up the environment by running the following command:

```bash
docker-compose up -d
```

On first startup, the database will be empty and the Postgis extension will not be installed. To install the extension,
run the following command:

```bash
docker-compose exec db psql -U root -d postgres -c "CREATE EXTENSION postgis;"
```

It is normal for **rldownload** and **rlpredict** to be stuck in a crash loop until the database is ready.

We will need to backfill the database with some data. To do this, run the following commands:

```bash
export DATABASE_URL=postgres://root:somepassword@localhost:5432/postgres
python download_historic_data.py
```

This will download the data from the API and insert it into the database.

## Usage

Now that the database is set up, you can start navigate to the frontend by
visiting [http://localhost:3000](http://localhost:3000). The default username is `admin` and the default password
is `admin` and setup the datasource in Grafana aswell as the Dashboard.


