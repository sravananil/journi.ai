from sqlalchemy import Column, String, Float, Integer, Text, JSON
from app.db.database import Base

class Place(Base):
    __tablename__ = "places"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    destination = Column(String, default="Goa", index=True)
    area = Column(String)  # North Goa, South Goa, Panjim, Old Goa, Central Goa
    category = Column(String)  # beach, fort, heritage, museum, restaurant, cafe, etc.
    
    latitude = Column(Float)
    longitude = Column(Float)
    
    interests = Column(JSON)  # List of strings e.g. ["food", "culture", "beaches"]
    suitable_for = Column(JSON)  # List of strings e.g. ["solo", "couple", "family"]
    
    opening_hours = Column(JSON, nullable=True)  # e.g., {"open": "09:00", "close": "18:00"} or None for 24/7
    duration = Column(Integer)  # recommended duration in minutes
    estimated_cost = Column(Integer)  # per person cost in INR
    
    best_time = Column(JSON)  # e.g. ["morning", "afternoon"]
    walking_level = Column(String)  # low, moderate, high
    indoor_outdoor = Column(String)  # indoor, outdoor, both
    
    description = Column(Text)
    source = Column(String, default="JOURNI Curated")
    confidence = Column(Float)
