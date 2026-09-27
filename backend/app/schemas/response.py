from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Literal, Optional
from datetime import date, datetime
from enum import Enum
from app.schemas.trip import TripRequest

class EvidenceType(str, Enum):
    FACT = "FACT"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"

class ValidationChecks(BaseModel):
    dates: bool
    schedule: bool
    opening_hours: bool
    geography: bool
    budget: bool
    traveller_suitability: bool
    duplicates: bool

class ValidationResult(BaseModel):
    passed: bool
    checks: Optional[ValidationChecks] = None

class TripSummary(BaseModel):
    estimated_cost: int
    major_activities: int
    estimated_travel_time: int
    meal_cost: int = 0
    estimated_known_total: int = 0

class JourneySummary(BaseModel):
    transport: str
    status: str
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None

class Activity(BaseModel):
    place_id: str
    name: str
    start_time: str
    end_time: str
    duration_minutes: int
    category: Optional[str] = None
    estimated_cost: int
    travel_minutes: int
    reason: str
    image_url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: Optional[str] = None

class NearbyRecommendation(BaseModel):
    place_id: str
    name: str
    category: Optional[str] = None
    distance_km: float
    travel_minutes: int
    reason: str
    source: Optional[str] = None
    distance_evidence: EvidenceType = EvidenceType.DERIVED
    place_evidence: EvidenceType = EvidenceType.FACT

class DailyItinerary(BaseModel):
    day: int
    date: date
    theme: str
    activities: List[Activity]
    limited_activities: bool = False
    recommendations: List[NearbyRecommendation] = Field(default_factory=list)

class TripInfo(BaseModel):
    destination: str
    start_date: date
    end_date: date
    nights: int

class AIExplanation(BaseModel):
    trip_summary: str
    why_this_fits: str
    day_explanations: Dict[int, str]

class MealSuggestion(BaseModel):
    meal: str
    restaurant: str
    cuisine: Optional[str] = None
    price: Optional[int] = None
    rating: Optional[float] = None
    source: str
    day: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    scheduled: bool = False

class EvidenceItem(BaseModel):
    label: str
    value: EvidenceType
    source: Optional[str] = None
    notes: Optional[str] = None

class TripResponse(BaseModel):
    trip: TripInfo
    days: List[DailyItinerary]
    summary: TripSummary
    assumptions: List[str]
    evidence: List[EvidenceItem] = Field(default_factory=list)
    validation: ValidationResult
    ai_explanation: Optional[AIExplanation] = None
    meal_suggestions: List[MealSuggestion] = Field(default_factory=list)
    journey: Optional[JourneySummary] = None

class ChatRequest(BaseModel):
    request: TripRequest
    itinerary: TripResponse
    question: str = Field(min_length=1, max_length=1000)
    current_day: Optional[int] = Field(default=None, ge=1)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("Question cannot be blank.")
        return question

class ChatResponse(BaseModel):
    answer: str
    requires_refinement: bool = False
    recommendations: List[NearbyRecommendation] = Field(default_factory=list)
    provider: Literal["gemini", "fallback"] = "fallback"

class AddRecommendationRequest(BaseModel):
    request: TripRequest
    itinerary: TripResponse
    day: int = Field(ge=1)
    place_id: str = Field(min_length=1, max_length=200)
