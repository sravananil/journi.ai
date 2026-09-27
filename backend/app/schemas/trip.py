from pydantic import BaseModel, model_validator
from typing import List, Optional, Dict
from enum import Enum
from datetime import date, datetime, time

class Location(BaseModel):
    city: str
    country: str
    lat: float
    lng: float

class Dates(BaseModel):
    start: date
    end: date
    nights: int

class TravellerType(str, Enum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"
    SENIORS = "seniors"

class Travellers(BaseModel):
    type: TravellerType
    adults: int
    children: List[int] = []
    seniors: int = 0

class Pace(str, Enum):
    EASY_GOING = "easy-going"
    BALANCED = "balanced"
    PACKED = "packed"

class Budget(str, Enum):
    BUDGET = "budget"
    MODERATE = "moderate"
    PREMIUM = "premium"
    LUXURY = "luxury"

class Transport(str, Enum):
    CAR = "car"
    TAXI = "taxi"
    PUBLIC = "public transport"
    SCOOTER = "scooter/bike"
    WALKING_PUBLIC = "walking + public transport"
    NO_PREFERENCE = "no preference"

class WalkingTolerance(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"

class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"

class JourneyTransport(str, Enum):
    TRAIN = "train"
    BUS = "bus"
    CAR = "car"
    TAXI = "taxi"
    PUBLIC = "public transport"
    SCOOTER = "scooter/bike"
    WALKING_PUBLIC = "walking + public transport"
    NO_PREFERENCE = "no preference"

class JourneyStatus(str, Enum):
    CONFIRMED = "confirmed"
    NOT_BOOKED = "not_booked"
    PLANNED = "planned"

class JourneyDetails(BaseModel):
    transport: JourneyTransport
    status: JourneyStatus
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_journey_window(self) -> "JourneyDetails":
        if (self.departure_at is None) != (self.arrival_at is None):
            raise ValueError("Provide both journey departure and arrival times, or neither.")
        if self.status in {JourneyStatus.CONFIRMED, JourneyStatus.PLANNED} and self.arrival_at is None:
            raise ValueError("Confirmed or planned journeys require departure and arrival times.")
        if self.departure_at is None or self.arrival_at is None:
            return self
        if self.departure_at.tzinfo is not None or self.arrival_at.tzinfo is not None:
            raise ValueError("Journey times must use the destination's local time without a timezone offset.")
        if self.arrival_at <= self.departure_at:
            raise ValueError("Journey arrival must be after departure.")
        return self

class TripRequest(BaseModel):
    origin: Location
    destination: Location
    dates: Dates
    arrival: TimeOfDay
    departure: TimeOfDay
    travellers: Travellers
    interests: Dict[str, float]
    pace: Pace
    transport: Transport
    budget: Budget
    dietary: List[str] = []
    walking_tolerance: WalkingTolerance
    avoid: List[str] = []
    day_start: time
    journey: Optional[JourneyDetails] = None

    @model_validator(mode="after")
    def validate_journey_arrival_date(self) -> "TripRequest":
        if self.journey and self.journey.arrival_at and self.journey.arrival_at.date() > self.dates.start:
            raise ValueError("Journey arrival must be on or before the itinerary start date.")
        return self

class RefineRequest(BaseModel):
    original_request: TripRequest
    refinement_prompt: str
