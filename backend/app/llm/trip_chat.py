import json
import logging
import re
from typing import Any

from app.llm.client import LLMClient
from app.schemas.response import ChatRequest, ChatResponse, NearbyRecommendation

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are JOURNI's itinerary explanation assistant.
The deterministic JOURNI planner is authoritative. Answer the user's question directly using only
the supplied trip request, current itinerary, activity metadata, evidence, assumptions, and
available recommendations. For selection questions, explain the actual places using supplied
traveller profile, interests, pace, budget, constraints, activity categories and reasons,
geographic grouping, scheduling feasibility, travel estimates, and dataset information when
available. Do not invent facts, places, prices, coordinates, opening hours, availability,
reservations, or selection criteria. If a reason is not present in the supplied data, say that it
is derived from JOURNI's planning logic rather than a verified fact. Distances and travel times are
derived estimates, not live routing. Only mention suggested places from available_recommendations;
if that list is empty, say no eligible suggestions were returned. Do not modify the itinerary.
When current_day is set, interpret "these places" as the activities in current_day_activities.
Explain only those selected activities and do not list activities from another day.
If the user asks to change, replace, add, remove, or reschedule activities, explain that Refine
Itinerary is the correct way to make changes. Keep the answer concise, warm, and specific to the
question rather than merely repeating the schedule.
"""


def request_changes_itinerary(question: str) -> bool:
    normalized = " ".join(question.lower().split())
    return bool(re.search(
        r"\b(replace|swap|remove|delete|add|insert|reschedule|move|replan|update|change)\b"
        r"|\b(make|keep)\b.{0,35}\b(relaxed|less busy|lighter|more cultural|more outdoors)\b"
        r"|\bmore relaxed (?:evening|day|schedule)\b",
        normalized,
    ))


def asks_for_places(question: str) -> bool:
    normalized = question.lower()
    return any(
        phrase in normalized
        for phrase in ("nearby", "recommend", "suggest a place", "suggest something", "what else can i visit")
    )


def asks_for_day_suggestions(question: str) -> bool:
    return bool(re.search(
        r"\b(what can i do|what should i do|things to do|activities? for|activities? on)\b",
        question.lower(),
    ))


def requested_day_number(question: str, current_day: int | None, available_days: list[int]) -> int:
    match = re.search(r"\bday\s+(\d+)\b", question.lower())
    if match:
        return int(match.group(1))
    return current_day or (available_days[0] if available_days else 1)


def _fallback_answer(payload: ChatRequest, recommendations: list[NearbyRecommendation]) -> str:
    if payload.itinerary.assumptions and any(
        token in payload.question.lower() for token in ("assumption", "unknown", "not verified")
    ):
        return "For this trip, JOURNI is assuming: " + " ".join(payload.itinerary.assumptions[:4])

    match = next(
        (
            activity
            for itinerary_day in payload.itinerary.days
            for activity in itinerary_day.activities
            if activity.name.lower() in payload.question.lower()
        ),
        None,
    )
    if match:
        return f"{match.name} was selected because {match.reason.lower()} The itinerary places it at {match.start_time}–{match.end_time}."

    if asks_for_day_suggestions(payload.question):
        day_number = requested_day_number(
            payload.question,
            payload.current_day,
            [item.day for item in payload.itinerary.days],
        )
        day = next(
            (item for item in payload.itinerary.days if item.day == day_number),
            None,
        )
        if day and day.activities:
            activities = "; ".join(
                f"{activity.start_time}–{activity.end_time} {activity.name}"
                for activity in day.activities
            )
            return f"Day {day.day} in {payload.request.destination.city} includes {activities}."
    if asks_for_places(payload.question) or asks_for_day_suggestions(payload.question):
        if recommendations:
            options = "; ".join(
                f"{item.name} ({item.distance_km:.1f} km, about {item.travel_minutes} min travel)"
                for item in recommendations
            )
            return (
                "Eligible nearby JOURNI dataset options are: "
                f"{options}. Distance and travel time are derived estimates."
            )
        if asks_for_day_suggestions(payload.question):
            day_number = requested_day_number(
                payload.question,
                payload.current_day,
                [item.day for item in payload.itinerary.days],
            )
            return (
                f"Day {day_number} has no eligible nearby dataset suggestions "
                "that fit its remaining time and trip constraints."
            )
        return (
            "JOURNI could not find an eligible nearby dataset suggestion for this day "
            "that fits the remaining time and trip constraints."
        )

    day_number = requested_day_number(
        payload.question, payload.current_day, [day.day for day in payload.itinerary.days]
    )
    day = next(
        (item for item in payload.itinerary.days if item.day == day_number),
        None,
    )
    if day and day.activities:
        activities = "; ".join(
            f"{activity.start_time}–{activity.end_time} {activity.name}"
            for activity in day.activities
        )
        return f"Day {day.day} in {payload.request.destination.city} includes {activities}. Its theme is {day.theme}."
    if day:
        if recommendations:
            names = ", ".join(item.name for item in recommendations)
            return f"Day {day.day} has limited scheduled activities. Nearby JOURNI dataset options are: {names}."
        return f"Day {day.day} has limited scheduled activities, and no suitable nearby dataset options fit its remaining time and constraints."

    if recommendations:
        return "Nearby JOURNI dataset options for this day are: " + ", ".join(
            item.name for item in recommendations
        ) + ". Their distances and travel times are estimates."
    return (
        f"This itinerary is for {payload.request.destination.city} from "
        f"{payload.itinerary.trip.start_date} to {payload.itinerary.trip.end_date}. "
        "I can answer from the listed schedule, assumptions, and evidence."
    )


class TripChat:
    @staticmethod
    def answer(
        payload: ChatRequest,
        recommendations: list[NearbyRecommendation],
    ) -> ChatResponse:
        if request_changes_itinerary(payload.question):
            return ChatResponse(
                answer="I won't change the itinerary from chat. Use Refine Itinerary to request that change; JOURNI will re-plan and validate it.",
                requires_refinement=True,
                provider="fallback",
            )

        day = next(
            (
                item for item in payload.itinerary.days
                if item.day == (payload.current_day or 0)
            ),
            None,
        )
        context: dict[str, Any] = {
            "trip_request": {
                "origin": payload.request.origin.model_dump(mode="json"),
                "destination": payload.request.destination.model_dump(mode="json"),
                "dates": payload.request.dates.model_dump(mode="json"),
                "journey": payload.request.journey.model_dump(mode="json") if payload.request.journey else None,
                "travellers": payload.request.travellers.model_dump(mode="json"),
                "interests": payload.request.interests,
                "pace": payload.request.pace.value,
                "budget": payload.request.budget.value,
                "transport": payload.request.transport.value,
                "dietary": payload.request.dietary,
                "avoid": payload.request.avoid,
                "walking_tolerance": payload.request.walking_tolerance.value,
                "arrival_period": payload.request.arrival.value,
                "departure_period": payload.request.departure.value,
                "preferred_day_start": payload.request.day_start.isoformat(),
            },
            "itinerary": {
                "summary": payload.itinerary.summary.model_dump(mode="json"),
                "journey": (
                    payload.itinerary.journey.model_dump(mode="json")
                    if payload.itinerary.journey else None
                ),
                "days": [
                    {
                        "day": item.day,
                        "date": item.date.isoformat(),
                        "theme": item.theme,
                        "limited_activities": item.limited_activities,
                        "planner_day_explanation": (
                            payload.itinerary.ai_explanation.day_explanations.get(
                                str(item.day)
                            )
                            if payload.itinerary.ai_explanation
                            else None
                        ),
                        "activities": [
                            {
                                "name": activity.name,
                                "category": activity.category,
                                "start": activity.start_time,
                                "end": activity.end_time,
                                "duration_minutes": activity.duration_minutes,
                                "travel_minutes": activity.travel_minutes,
                                "reason": activity.reason,
                                "coordinates": [activity.lat, activity.lng],
                                "source": activity.source,
                                "estimated_cost": activity.estimated_cost,
                            }
                            for activity in item.activities[:12]
                        ],
                    }
                    for item in payload.itinerary.days[:21]
                ],
                "assumptions": payload.itinerary.assumptions[:20],
                "evidence": [
                    item.model_dump(mode="json") for item in payload.itinerary.evidence[:20]
                ],
                "meal_suggestions": [
                    item.model_dump(mode="json")
                    for item in payload.itinerary.meal_suggestions[:20]
                ],
                "validation_passed": payload.itinerary.validation.passed,
            },
            "current_day": day.day if day else None,
            "current_day_activities": [
                {
                    "name": activity.name,
                    "category": activity.category,
                    "reason": activity.reason,
                    "start": activity.start_time,
                    "end": activity.end_time,
                    "travel_minutes": activity.travel_minutes,
                }
                for activity in day.activities[:12]
            ] if day else [],
            "available_recommendations": [
                item.model_dump(mode="json") for item in recommendations
            ],
            "question": payload.question,
        }
        prompt = json.dumps(context, ensure_ascii=True, separators=(",", ":"))

        answer = LLMClient.get_instance().generate_text(CHAT_SYSTEM_PROMPT, prompt)
        provider = "gemini" if answer else "fallback"
        if answer is None:
            logger.warning("CHAT provider=fallback")
        else:
            logger.info("CHAT provider=gemini")
        return ChatResponse(
            answer=answer[:3000] if answer else _fallback_answer(payload, recommendations),
            requires_refinement=False,
            recommendations=recommendations,
            provider=provider,
        )
