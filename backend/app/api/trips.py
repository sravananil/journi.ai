from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.trip import TripRequest, RefineRequest
from app.schemas.response import (
    AddRecommendationRequest,
    ChatRequest,
    ChatResponse,
    TripResponse,
)
from app.planner.engine import PlanningEngine
from app.llm.explainer import LLMExplainer
from app.llm.refiner import LLMRefiner, RefinementCommand
from app.llm.trip_chat import TripChat, requested_day_number
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def _validate_current_itinerary(request: TripRequest, itinerary: TripResponse) -> None:
    if (
        itinerary.trip.destination != request.destination.city
        or itinerary.trip.start_date != request.dates.start
        or itinerary.trip.end_date != request.dates.end
    ):
        raise HTTPException(
            status_code=422,
            detail="The itinerary does not match the supplied current trip request.",
        )


@router.post("/plan", response_model=TripResponse)
def plan_trip(request: TripRequest, db: Session = Depends(get_db)):
    try:
        engine = PlanningEngine(db)
        response = engine.plan_trip(request)
        
        # LLM Explanation Fallback
        try:
            explanation = LLMExplainer.generate_explanation(request, response)
            if explanation:
                response.ai_explanation = explanation
        except Exception as e:
            logger.error(f"Explanation failed, gracefully degrading: {e}")
            
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
def chat_about_trip(payload: ChatRequest, db: Session = Depends(get_db)):
    _validate_current_itinerary(payload.request, payload.itinerary)
    if payload.current_day is not None and not any(
        day.day == payload.current_day for day in payload.itinerary.days
    ):
        raise HTTPException(status_code=422, detail="The requested current day is not in this itinerary.")

    try:
        engine = PlanningEngine(db)
        available_days = [day.day for day in payload.itinerary.days]
        day_number = requested_day_number(
            payload.question, payload.current_day, available_days
        )
        if day_number not in available_days:
            return ChatResponse(
                answer=f"This itinerary has {len(available_days)} days; Day {day_number} is not part of this trip."
            )
        recommendations = engine.recommendations_for_day(
            payload.request, payload.itinerary, day_number
        )
        return TripChat.answer(payload, recommendations)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Itinerary chat failed.")
        raise HTTPException(status_code=500, detail="JOURNI could not answer about this itinerary.") from exc


@router.post("/recommendations/add", response_model=TripResponse)
def add_recommendation(payload: AddRecommendationRequest, db: Session = Depends(get_db)):
    _validate_current_itinerary(payload.request, payload.itinerary)
    if not any(day.day == payload.day for day in payload.itinerary.days):
        raise HTTPException(status_code=422, detail="The selected itinerary day does not exist.")
    if any(
        activity.place_id == payload.place_id
        for day in payload.itinerary.days
        for activity in day.activities
    ):
        raise HTTPException(status_code=409, detail="This place is already in the itinerary.")

    try:
        engine = PlanningEngine(db)
        candidates = engine.retrieval.retrieve(payload.request)
        valid_candidates = engine.constraints.filter_candidates(payload.request, candidates)
        place = next((item for item in valid_candidates if item.id == payload.place_id), None)
        if place is None:
            raise HTTPException(status_code=404, detail="This place is no longer an eligible JOURNI recommendation.")
        current_options = engine.recommendations_for_day(
            payload.request, payload.itinerary, payload.day
        )
        if not any(item.place_id == payload.place_id for item in current_options):
            raise HTTPException(
                status_code=409,
                detail="The recommendation no longer satisfies this day's distance, time, or budget constraints.",
            )

        updated = engine.plan_trip(
            payload.request,
            refinement_context={
                "action": "add_recommendation",
                "target_day": payload.day,
                "place_id": payload.place_id,
            },
        )
        if not updated.validation.passed or not any(
            day.day == payload.day
            and any(activity.place_id == payload.place_id for activity in day.activities)
            for day in updated.days
        ):
            raise HTTPException(
                status_code=409,
                detail="The deterministic planner could not fit this recommendation without a schedule conflict.",
            )
        try:
            explanation = LLMExplainer.generate_explanation(payload.request, updated)
            if explanation:
                updated.ai_explanation = explanation
        except Exception:
            logger.exception("Post-add explanation failed; returning the validated deterministic itinerary.")
        return updated
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Adding an itinerary recommendation failed.")
        raise HTTPException(status_code=500, detail="JOURNI could not add this recommendation.") from exc


def _apply_refinement_commands(req: TripRequest, commands: list[RefinementCommand]) -> tuple[TripRequest, dict]:
    """
    Deterministically mutate a TripRequest based on RefinementCommands.
    
    Returns:
        (mutated_request, repair_context)
        
    This function contains all deterministic mutation logic.
    Gemini only produces the command list — this function executes them.
    """
    from app.schemas.trip import Pace

    repair_context = {"reduce_density": False, "reduce_distance": False, "target_day": None}
    
    for cmd in commands:
        action = cmd.action
        
        if action == "increase_trip_days":
            delta = abs(cmd.days_delta) if cmd.days_delta else 1
            # Clamp to max +7 per refinement 
            delta = min(delta, 7)
            new_nights = req.dates.nights + delta
            new_end = req.dates.start + timedelta(days=new_nights)
            # Use model_copy to create a valid new Dates object
            from app.schemas.trip import Dates
            req.dates = Dates(start=req.dates.start, end=new_end, nights=new_nights)
            logger.info(f"Refinement: Increased trip days by {delta}. New nights: {new_nights}")
            
        elif action == "decrease_trip_days":
            delta = abs(cmd.days_delta) if cmd.days_delta else 1
            # Clamp: cannot reduce below 1 night / 2 days
            new_nights = max(1, req.dates.nights - delta)
            new_end = req.dates.start + timedelta(days=new_nights)
            from app.schemas.trip import Dates
            req.dates = Dates(start=req.dates.start, end=new_end, nights=new_nights)
            logger.info(f"Refinement: Decreased trip days by {delta}. New nights: {new_nights}")
            
        elif action == "change_pace":
            if cmd.target_value:
                try:
                    req.pace = Pace(cmd.target_value)
                    logger.info(f"Refinement: Changed pace to {cmd.target_value}")
                    if cmd.target_value == "easy-going":
                        repair_context["reduce_density"] = True
                    elif cmd.target_value == "packed":
                        repair_context["reduce_density"] = False
                except ValueError:
                    logger.warning(f"Refinement: Invalid pace value '{cmd.target_value}', skipping.")
                    
        elif action == "avoid_category":
            if cmd.target_value and cmd.target_value not in req.avoid:
                req.avoid.append(cmd.target_value)
                logger.info(f"Refinement: Added avoid category '{cmd.target_value}'")
                
        elif action == "reduce_day_density":
            repair_context["reduce_density"] = True
            if cmd.day > 0:
                repair_context["target_day"] = cmd.day
            logger.info(f"Refinement: Reduce density, day={cmd.day}")
            
        elif action == "increase_day_density":
            repair_context["reduce_density"] = False
            logger.info(f"Refinement: Increase density")
            
        elif action == "change_interest_focus":
            if cmd.target_value:
                interest = cmd.target_value.lower()
                # Boost the interest weight — don't fabricate, just emphasize
                existing = req.interests.get(interest, 0.5)
                req.interests[interest] = min(1.0, existing + 0.3)
                logger.info(f"Refinement: Boosted interest '{interest}' to {req.interests[interest]}")
                
    return req, repair_context


@router.post("/refine", response_model=TripResponse)
def refine_trip(request: RefineRequest, db: Session = Depends(get_db)):
    """
    Refinement endpoint.
    
    Flow:
      1. Gemini interprets the natural-language request → MultiRefinementCommand
      2. Commands are applied deterministically to mutate TripRequest
      3. PlanningEngine re-generates the itinerary from scratch using the mutated request
      4. Gemini generates a new explanation
      5. Updated TripResponse returned
      
    Gemini NEVER writes the final itinerary. The deterministic planner does.
    """
    try:
        # 1. Gemini interpretation
        multi_command = None
        gemini_available = True
        
        try:
            multi_command = LLMRefiner.interpret(request.refinement_prompt)
        except Exception as e:
            logger.error(f"Gemini refinement interpretation failed: {e}")
            gemini_available = False
            
        req = request.original_request
        repair_context = {"reduce_density": False, "reduce_distance": False, "target_day": None}

        if multi_command and multi_command.commands:
            logger.info(f"Gemini interpreted {len(multi_command.commands)} refinement command(s).")
            req, repair_context = _apply_refinement_commands(req, multi_command.commands)
        elif not gemini_available or not multi_command:
            # Gemini unavailable or returned nothing — try simple deterministic fallback
            # for the most obvious refinement patterns
            prompt_lower = request.refinement_prompt.lower()
            fallback_commands = []
            
            import re
            # Duration changes
            add_match = re.search(r'add\s+(\d+)\s+(more\s+)?day', prompt_lower)
            remove_match = re.search(r'(remove|reduce|cut).*?(\d+)\s+day', prompt_lower)
            if add_match:
                from app.llm.refiner import RefinementCommand
                fallback_commands.append(RefinementCommand(
                    action="increase_trip_days", day=0, days_delta=int(add_match.group(1))
                ))
            if remove_match:
                from app.llm.refiner import RefinementCommand
                fallback_commands.append(RefinementCommand(
                    action="decrease_trip_days", day=0, days_delta=-int(remove_match.group(2))
                ))
            if 'relaxed' in prompt_lower or 'relax' in prompt_lower:
                from app.llm.refiner import RefinementCommand
                fallback_commands.append(RefinementCommand(
                    action="change_pace", day=0, target_value="easy-going"
                ))
            if 'adventurous' in prompt_lower or 'adventure' in prompt_lower:
                from app.llm.refiner import RefinementCommand
                fallback_commands.append(RefinementCommand(
                    action="change_interest_focus", day=0, target_value="adventure"
                ))
                
            if fallback_commands:
                logger.info(f"Using deterministic fallback with {len(fallback_commands)} commands (Gemini unavailable).")
                req, repair_context = _apply_refinement_commands(req, fallback_commands)
            else:
                logger.warning("Refinement: Gemini unavailable and no deterministic fallback matched. Re-running planner with unchanged request.")

        # 2. Re-plan deterministically with the mutated request
        engine = PlanningEngine(db)
        response = engine.plan_trip(req, refinement_context=repair_context)

        # 3. Re-explain with the updated itinerary
        try:
            explanation = LLMExplainer.generate_explanation(req, response)
            if explanation:
                response.ai_explanation = explanation
        except Exception as e:
            logger.error(f"Refinement explanation failed, gracefully degrading: {e}")
            
        return response
    except Exception as e:
        logger.error(f"Refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
