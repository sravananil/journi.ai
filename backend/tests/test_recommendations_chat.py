import json
from datetime import date, time

from app.llm import explainer, trip_chat
from app.llm.explainer import ExplanationOutput, LLMExplainer
from app.api import trips as trip_api
from app.models.place import Place
from app.planner.recommendations import RecommendationService, RecommendationSettings
from app.planner.engine import PlanningEngine
from app.planner.timing import PlannerTiming
from app.schemas.response import (
    Activity,
    AddRecommendationRequest,
    ChatRequest,
    DailyItinerary,
    MealSuggestion,
    NearbyRecommendation,
    TripInfo,
    TripResponse,
    TripSummary,
    ValidationResult,
)
from app.schemas.trip import (
    Budget,
    Dates,
    Location,
    Pace,
    TimeOfDay,
    Transport,
    Travellers,
    TripRequest,
    WalkingTolerance,
)


def make_request(
    transport: Transport = Transport.CAR,
    budget: Budget = Budget.MODERATE,
) -> TripRequest:
    return TripRequest(
        origin=Location(city="Kurnool", country="India", lat=15.8281, lng=78.0373),
        destination=Location(city="Visakhapatnam", country="India", lat=17.6868, lng=83.2185),
        dates=Dates(start=date(2026, 10, 1), end=date(2026, 10, 3), nights=2),
        arrival=TimeOfDay.MORNING,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type="solo", adults=1),
        interests={"nature": 1.0, "culture": 0.8},
        pace=Pace.BALANCED,
        transport=transport,
        budget=budget,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start=time(9, 0),
    )


def make_activity(place_id: str, name: str, end_time: str = "16:45") -> Activity:
    return Activity(
        place_id=place_id,
        name=name,
        start_time="15:45",
        end_time=end_time,
        duration_minutes=60,
        category="nature",
        estimated_cost=0,
        travel_minutes=0,
        reason="Selected for its nature matching your profile.",
        lat=17.6868,
        lng=83.2185,
    )


def make_response(activity: Activity | None = None, estimated_cost: int = 0) -> TripResponse:
    activities = [activity] if activity else []
    return TripResponse(
        trip=TripInfo(
            destination="Visakhapatnam",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 3),
            nights=2,
        ),
        days=[
            DailyItinerary(
                day=1,
                date=date(2026, 10, 1),
                theme="Coastal nature",
                activities=activities,
            ),
            DailyItinerary(
                day=2,
                date=date(2026, 10, 2),
                theme="Coastal nature",
                activities=[make_activity("visited", "Kailasagiri")],
            ),
            DailyItinerary(
                day=3,
                date=date(2026, 10, 3),
                theme="Coastal nature",
                activities=[],
            ),
        ],
        summary=TripSummary(
            estimated_cost=estimated_cost,
            major_activities=len(activities) + 1,
            estimated_travel_time=0,
        ),
        assumptions=["Opening hours are unknown."],
        validation=ValidationResult(passed=True),
    )


def make_place(
    place_id: str,
    longitude_offset: float,
    *,
    interests: list[str] | None = None,
    duration: int = 60,
    cost: int = 0,
    opening_hours: dict[str, str] | None = None,
) -> Place:
    return Place(
        id=place_id,
        name=place_id.title(),
        destination="Visakhapatnam",
        category="nature",
        latitude=17.6868,
        longitude=83.2185 + longitude_offset,
        interests=interests or ["nature"],
        duration=duration,
        estimated_cost=cost,
        opening_hours=opening_hours,
        source="JOURNI dataset",
    )


def test_car_recommendation_radius_tightens_during_evening_window():
    settings = RecommendationSettings()

    assert settings.radius_for(Transport.CAR, time(16, 59)) == 10
    assert settings.radius_for(Transport.CAR, time(17, 0)) == 7
    assert settings.radius_for(Transport.SCOOTER, time(18, 59)) == 7
    assert settings.radius_for(Transport.CAR, time(19, 0)) == 10


def test_recommendations_use_last_stop_remove_visited_and_rank_supported_places():
    request = make_request()
    response = make_response(make_activity("last-stop", "Last stop"))
    day = response.days[1]
    service = RecommendationService(PlannerTiming())
    candidates = [
        (make_place("nearby", 0.03, interests=["nature"]), 1.0),
        (make_place("far", 0.09), 3.0),
        (make_place("visited", 0.01), 5.0),
    ]

    results = service.for_day(request, response, day, candidates)

    assert [item.place_id for item in results] == ["nearby"]
    assert results[0].distance_km > 3
    assert results[0].travel_minutes > 0
    assert results[0].place_evidence.value == "FACT"
    assert results[0].distance_evidence.value == "DERIVED"


def test_recommendations_respect_transport_time_opening_hours_and_budget():
    request = make_request(budget=Budget.BUDGET)
    response = make_response(estimated_cost=14900)
    day = response.days[1]
    service = RecommendationService(PlannerTiming())
    in_radius = make_place("fits", 0.03, cost=50)
    over_budget = make_place("too-expensive", 0.02, cost=200)
    closed_by_arrival = make_place(
        "closed", 0.01, opening_hours={"open": "09:00", "close": "17:00"}
    )

    results = service.for_day(
        request,
        response,
        day,
        [(in_radius, 1.0), (over_budget, 5.0), (closed_by_arrival, 4.0)],
    )

    assert [item.place_id for item in results] == ["fits"]
    assert RecommendationSettings().radius_for(
        Transport.WALKING_PUBLIC, time(12, 0)
    ) != RecommendationSettings().radius_for(Transport.TAXI, time(12, 0))


def test_recommendation_is_omitted_when_remaining_time_cannot_fit_return():
    request = make_request()
    response = make_response()
    response.days[1].activities = [
        make_activity("last-stop", "Last stop", end_time="21:30")
    ]
    service = RecommendationService(PlannerTiming())
    candidate = make_place("nearby", 0.01, duration=60)

    assert service.for_day(request, response, response.days[1], [(candidate, 1.0)]) == []


def test_candidate_arriving_during_evening_uses_the_tighter_radius():
    request = make_request()
    response = make_response()
    response.days[1].activities = [
        make_activity("last-stop", "Last stop", end_time="16:30")
    ]
    service = RecommendationService(PlannerTiming())
    candidate = make_place("evening-edge", 0.075)

    assert service.for_day(request, response, response.days[1], [(candidate, 1.0)]) == []


def test_chat_prompt_contains_current_trip_schedule_and_only_supplied_options(monkeypatch):
    request = make_request()
    response = make_response(make_activity("last-stop", "Kailasagiri"))
    payload = ChatRequest(
        request=request,
        itinerary=response,
        question="Why did you choose these places?",
        current_day=2,
    )
    recommendation = NearbyRecommendation(
        place_id="nearby",
        name="Nearby Place",
        category="nature",
        distance_km=2.5,
        travel_minutes=12,
        reason="Matches your nature interests.",
        source="JOURNI dataset",
    )

    class FakeGemini:
        prompt = ""
        system_instruction = ""

        def generate_text(self, system_instruction: str, prompt: str) -> str:
            self.system_instruction = system_instruction
            self.prompt = prompt
            return "The selected places match your stated interests and fit the day's schedule."

    fake = FakeGemini()
    monkeypatch.setattr(trip_chat.LLMClient, "get_instance", lambda: fake)

    result = trip_chat.TripChat.answer(payload, [recommendation])
    context = json.loads(fake.prompt)

    assert result.answer == "The selected places match your stated interests and fit the day's schedule."
    assert result.provider == "gemini"
    assert "answer the user's question directly" in fake.system_instruction.lower()
    assert context["trip_request"]["interests"] == {"nature": 1.0, "culture": 0.8}
    assert context["current_day"] == 2
    assert [item["name"] for item in context["current_day_activities"]] == ["Kailasagiri"]
    assert context["trip_request"]["origin"]["city"] == "Kurnool"
    assert context["trip_request"]["transport"] == "car"
    assert context["itinerary"]["days"][1]["activities"][0]["name"] == "Kailasagiri"
    assert context["available_recommendations"][0]["name"] == "Nearby Place"


def test_chat_recommendation_answer_uses_only_deterministic_dataset_options(monkeypatch):
    request = make_request()
    response = make_response()

    class FakeGemini:
        prompt = ""

        def generate_text(self, _system_instruction, prompt):
            self.prompt = prompt
            return "Dataset Place is one of the eligible options returned by the planner."

    fake = FakeGemini()
    monkeypatch.setattr(trip_chat.LLMClient, "get_instance", lambda: fake)
    result = trip_chat.TripChat.answer(
        ChatRequest(
            request=request,
            itinerary=response,
            question="Can you suggest something nearby?",
            current_day=2,
        ),
        [
            NearbyRecommendation(
                place_id="dataset-place",
                name="Dataset Place",
                category="nature",
                distance_km=2.5,
                travel_minutes=12,
                reason="Matches your nature interests.",
                source="JOURNI dataset",
            )
        ],
    )

    assert "Dataset Place" in result.answer
    assert result.provider == "gemini"
    assert json.loads(fake.prompt)["available_recommendations"][0]["distance_km"] == 2.5
    assert [item.name for item in result.recommendations] == ["Dataset Place"]


def test_chat_day_suggestion_uses_the_referenced_day_not_the_selected_day(monkeypatch):
    request = make_request()
    response = make_response()
    state: dict[str, int] = {}

    class FakeEngine:
        def __init__(self, _db):
            pass

        def recommendations_for_day(self, _request, _itinerary, day_number):
            state["day"] = day_number
            return []

    monkeypatch.setattr(trip_api, "PlanningEngine", FakeEngine)
    monkeypatch.setattr(
        trip_chat.LLMClient,
        "get_instance",
        lambda: type("NoGemini", (), {"generate_text": lambda *_: None})(),
    )
    result = trip_api.chat_about_trip(
        ChatRequest(
            request=request,
            itinerary=response,
            question="What can I do on Day 3?",
            current_day=1,
        ),
        db=None,
    )

    assert state["day"] == 3
    assert "Day 3" in result.answer
    assert not result.requires_refinement
    assert result.provider == "fallback"


def test_explainer_schema_uses_supported_array_for_day_summaries(monkeypatch):
    request = make_request()
    response = make_response()
    schema = ExplanationOutput.model_json_schema()
    day_schema = schema["properties"]["day_explanations"]
    assert day_schema["type"] == "array"

    class FakeGemini:
        def generate_structured(self, *, system_instruction, prompt, schema):
            assert system_instruction
            assert prompt
            assert schema is ExplanationOutput
            return ExplanationOutput(
                trip_summary="A coastal nature trip.",
                why_this_fits="It follows the selected nature interest.",
                day_explanations=[
                    {"day": 1, "explanation": "Explore coastal nature."}
                ],
            )

    monkeypatch.setattr(
        explainer.LLMClient,
        "get_instance",
        lambda: FakeGemini(),
    )
    explanation = LLMExplainer.generate_explanation(request, response)

    assert explanation is not None
    assert explanation.day_explanations == {1: "Explore coastal nature."}


def test_add_recommendation_routes_through_deterministic_planner(monkeypatch):
    request = make_request()
    itinerary = make_response()
    place = make_place("new-dataset-place", 0.01)
    recommendation = NearbyRecommendation(
        place_id=place.id,
        name=place.name,
        category=place.category,
        distance_km=1.1,
        travel_minutes=8,
        reason="Matches your nature interests.",
        source="JOURNI dataset",
    )
    state: dict[str, object] = {}

    class FakeEngine:
        def __init__(self, _db):
            self.retrieval = type("Retrieval", (), {"retrieve": lambda _self, _request: [place]})()
            self.constraints = type(
                "Constraints", (), {"filter_candidates": lambda _self, _request, values: values}
            )()

        def recommendations_for_day(self, _request, _itinerary, _day):
            return [recommendation]

        def plan_trip(self, _request, refinement_context):
            state["refinement_context"] = refinement_context
            updated = itinerary.model_copy(deep=True)
            updated.days[1].activities.append(
                Activity(
                    place_id=place.id,
                    name=place.name,
                    start_time="17:00",
                    end_time="18:00",
                    duration_minutes=60,
                    category=place.category,
                    estimated_cost=0,
                    travel_minutes=8,
                    reason="Added by deterministic scheduling.",
                    lat=place.latitude,
                    lng=place.longitude,
                )
            )
            updated.summary.major_activities += 1
            return updated

    monkeypatch.setattr(trip_api, "PlanningEngine", FakeEngine)
    monkeypatch.setattr(trip_api.LLMExplainer, "generate_explanation", lambda *_: None)

    result = trip_api.add_recommendation(
        AddRecommendationRequest(
            request=request,
            itinerary=itinerary,
            day=2,
            place_id=place.id,
        ),
        db=None,
    )

    assert state["refinement_context"] == {
        "action": "add_recommendation",
        "target_day": 2,
        "place_id": place.id,
    }
    assert any(activity.place_id == place.id for activity in result.days[1].activities)
    assert result.validation.passed


def test_engine_schedules_added_place_and_validates_without_duplicates(monkeypatch):
    request = make_request()
    existing = make_place("scheduled-place", 0.0)
    added = make_place("added-place", 0.004)
    engine = PlanningEngine(db=None)
    engine.retrieval.retrieve = lambda _request: [existing, added]

    class OneDayCluster:
        def cluster_places_for_days(self, _request, _scored, num_days, _repair):
            return {day: ([existing] if day == 1 else []) for day in range(1, num_days + 1)}

    engine.geography = OneDayCluster()
    def add_test_meal(response, _db, _city, _dietary, _request=None):
        response.meal_suggestions = [
            MealSuggestion(
                meal="Lunch (Day 1)",
                restaurant="Test Restaurant",
                price=450,
                source="Test",
                day=1,
                start_time="12:30",
                end_time="13:30",
                scheduled=True,
            )
        ]
        return response

    monkeypatch.setattr(
        "app.planner.meal_service.MealSuggestionService.enrich",
        add_test_meal,
    )

    response = engine.plan_trip(
        request,
        refinement_context={
            "action": "add_recommendation",
            "target_day": 1,
            "place_id": added.id,
        },
    )
    scheduled_ids = [
        activity.place_id
        for day in response.days
        for activity in day.activities
    ]

    assert response.validation.passed
    assert scheduled_ids.count(added.id) == 1
    assert scheduled_ids.count(existing.id) == 1
    assert response.days[0].activities[-1].place_id == added.id
    assert response.summary.meal_cost == 450
    assert response.summary.estimated_known_total == response.summary.estimated_cost + 450


def test_chat_fallback_answers_from_itinerary_and_routes_changes_to_refinement(monkeypatch):
    request = make_request()
    response = make_response(make_activity("last-stop", "Kailasagiri"))
    monkeypatch.setattr(
        trip_chat.LLMClient,
        "get_instance",
        lambda: type("NoGemini", (), {"generate_text": lambda *_: None})(),
    )
    grounded = trip_chat.TripChat.answer(
        ChatRequest(request=request, itinerary=response, question="Why Kailasagiri?"),
        [],
    )
    change = trip_chat.TripChat.answer(
        ChatRequest(
            request=request,
            itinerary=response,
            question="Can I have a more relaxed evening?",
        ),
        [],
    )

    assert "Kailasagiri" in grounded.answer
    assert "nature" in grounded.answer
    assert grounded.provider == "fallback"
    assert change.requires_refinement
    assert "Refine Itinerary" in change.answer
