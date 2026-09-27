from sqlalchemy.orm import Session
from app.models.place import Place
from app.schemas.trip import TripRequest
from app.planner.tracer import PlannerTracer
from typing import List

class CandidateRetrieval:
    def __init__(self, db: Session, tracer: PlannerTracer):
        self.db = db
        self.tracer = tracer

    def retrieve(self, request: TripRequest) -> List[Place]:
        from app.models.city import City
        
        req_city_lower = request.destination.city.strip().lower()
        
        # 1. City Alias Resolution
        # We need to find the canonical city. Since SQLite doesn't have great JSON array searching,
        # we can fetch cities that might match and check in Python (table is small enough).
        # We fetch exact matches first
        canonical_city_name = request.destination.city
        
        db_city = self.db.query(City).filter(
            (City.name == request.destination.city) | 
            (City.normalized_name == req_city_lower)
        ).first()
        
        if not db_city:
            # Fallback to checking aliases
            all_cities = self.db.query(City).all()
            for c in all_cities:
                if c.aliases and req_city_lower in [str(a).lower() for a in c.aliases]:
                    db_city = c
                    break
                    
        if db_city:
            canonical_city_name = db_city.name
            self.tracer.add_trace(
                stage="Retrieval",
                action="City Normalization",
                details=f"Resolved '{request.destination.city}' to canonical city '{canonical_city_name}'"
            )
        else:
            self.tracer.add_trace(
                stage="Retrieval",
                action="City Normalization",
                details=f"Could not resolve '{request.destination.city}' to a known canonical city."
            )
            # If we strictly want to return empty for unknown cities
            return []
            
        # Match Place.destination against the exact canonical name OR its aliases (case-insensitive)
        valid_destinations = [canonical_city_name.lower(), db_city.normalized_name.lower()]
        if db_city.aliases:
            valid_destinations.extend([str(a).lower() for a in db_city.aliases])
            
        from sqlalchemy import func
        places = self.db.query(Place).filter(func.lower(Place.destination).in_(valid_destinations)).all()
        
        self.tracer.add_trace(
            stage="Retrieval",
            action="Fetch candidates",
            details=f"Retrieved {len(places)} places for {canonical_city_name} (including aliases)"
        )
        return places
