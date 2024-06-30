from geoalchemy2 import Geometry
from sqlalchemy import Column, String, ForeignKey, TIMESTAMP, REAL
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Box(Base):
    __tablename__ = "boxes"
    id = Column(String, primary_key=True)
    model = Column(String)
    name = Column(String)
    location = Column(Geometry(geometry_type='POINT', srid=4326))
    exposure = Column(String)


class Sensor(Base):
    __tablename__ = "sensors"
    id = Column(String, primary_key=True)
    box_id = Column(String, ForeignKey("boxes.id"))
    icon = Column(String)
    title = Column(String)
    unit = Column(String)
    sensor_type = Column(String)


class Data(Base):
    __tablename__ = "data"
    box_id = Column(String, ForeignKey("boxes.id"), primary_key=True)
    sensor_id = Column(String, ForeignKey("sensors.id"), primary_key=True)
    timestamp = Column(TIMESTAMP, primary_key=True)
    value = Column(REAL)


class Prediction(Base):
    __tablename__ = "predictions"
    box_id = Column(String, ForeignKey("boxes.id"), primary_key=True)
    sensor_id = Column(String, ForeignKey("sensors.id"), primary_key=True)
    timestamp = Column(TIMESTAMP, primary_key=True)
    value = Column(REAL)
