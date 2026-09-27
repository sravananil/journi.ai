from sqlalchemy import Column, String, Float, Integer, Boolean, Text
from app.db.database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    city = Column(String, index=True)
    area = Column(String)
    address = Column(Text)
    
    cuisine = Column(String)  # comma separated list or just raw string
    rating = Column(Float)
    rating_count = Column(String)  # e.g., "100+ ratings"
    
    price_level = Column(String)  # budget, moderate, premium
    cost = Column(Integer)
    is_pure_veg = Column(Boolean)
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    source = Column(String)
