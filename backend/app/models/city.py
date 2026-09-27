from sqlalchemy import Column, String, Float, Integer, JSON
from app.db.database import Base

class City(Base):
    __tablename__ = "cities"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    state = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    population = Column(Integer)
    aliases = Column(JSON)
    source = Column(String)
