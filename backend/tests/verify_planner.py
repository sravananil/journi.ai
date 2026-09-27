import asyncio
import json
from datetime import date
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, TimeOfDay, WalkingTolerance
from app.planner.engine import PlanningEngine

from app.db.database import SessionLocal

async def run_verification():
    db = SessionLocal()
    try:
        engine = PlanningEngine(db=db)
        
        destinations = [
            {"city": "Bengaluru", "lat": 12.9716, "lng": 77.5946},
            {"city": "Delhi", "lat": 28.6139, "lng": 77.2090},
            {"city": "Manali", "lat": 32.2396, "lng": 77.1887},
            {"city": "Goa", "lat": 15.2993, "lng": 74.1240}
        ]
        
        for dest in destinations:
            print(f"\n======================================")
            print(f"VERIFYING PLANNER FOR: {dest['city']}")
            print(f"======================================")
            
            req = TripRequest(
                origin=Location(city="Mumbai", country="India", lat=19.0760, lng=72.8777),
                destination=Location(city=dest['city'], country="India", lat=dest['lat'], lng=dest['lng']),
                dates=Dates(start=date(2026, 10, 1), end=date(2026, 10, 3), nights=2),
                arrival=TimeOfDay.MORNING,
                departure=TimeOfDay.EVENING,
                travellers=Travellers(type="family", adults=2, children=[10], seniors=0),
                interests={"culture": 0.8, "nature": 1.0, "food": 0.9},
                pace=Pace.BALANCED,
                transport=Transport.CAR,
                budget=Budget.MODERATE,
                dietary=[],
                walking_tolerance=WalkingTolerance.MODERATE,
                avoid=[],
                day_start="09:00"
            )
            
            try:
                plan = engine.plan_trip(req)
                print(f"SUCCESS: Generated {len(plan.days)} days.")
                print(f"Total Activities: {plan.summary.major_activities}")
                print(f"Estimated Cost: INR {plan.summary.estimated_cost}")
                print(f"Validation Passed: {plan.validation.passed}")
                print(f"Validation Details: {plan.validation.checks}")
                print(f"Meal Suggestions: {len(plan.meal_suggestions)}")
                for meal in plan.meal_suggestions:
                    print(f"    - {meal.meal}: {meal.restaurant} (Cuisine: {meal.cuisine}, Price: {meal.price}, Source: {meal.source})")
                print(f"Days Content:")
                for day in plan.days:
                    print(f"  Day {day.day}: {len(day.activities)} activities. Theme: {day.theme}")
                    for act in day.activities:
                        print(f"    - {act.name} (Start: {act.start_time}, End: {act.end_time}, Cat: {act.category})")
            except Exception as e:
                print(f"FAILED for {dest['city']}: {e}")
                import traceback
                traceback.print_exc()
                
    finally:
        db.close()
            
if __name__ == "__main__":
    asyncio.run(run_verification())
