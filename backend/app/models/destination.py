from sqlalchemy import Column, String, Float, Integer, Text, JSON, Boolean
from app.db.database import Base

class Destination(Base):
    __tablename__ = "destinations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    state = Column(String)
    district = Column(String)
    region = Column(String)
    
    latitude = Column(Float)
    longitude = Column(Float)
    altitude_m = Column(Float)
    
    popularity_score = Column(Float)
    accessibility = Column(String)
    nearest_airport = Column(String)
    nearest_railway_station = Column(String)
    nearest_major_city = Column(String)
    road_connectivity = Column(String)
    
    budget_daily_low = Column(Integer)
    budget_daily_high = Column(Integer)
    midrange_daily_low = Column(Integer)
    midrange_daily_high = Column(Integer)
    luxury_daily_low = Column(Integer)
    luxury_daily_high = Column(Integer)
    
    trip_types = Column(JSON)
    activities_available = Column(JSON)
    best_seasons = Column(JSON)
    ideal_for = Column(JSON)
    
    minimum_days = Column(Integer)
    ideal_days = Column(Integer)
    maximum_days = Column(Integer)
    
    food_scene = Column(Text)
    local_cuisine = Column(JSON)
    description = Column(Text)
    
    source = Column(String)
