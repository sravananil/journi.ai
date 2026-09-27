from typing import Optional, List
from pydantic import BaseModel
from app.schemas.response import TripResponse, AIExplanation
from app.schemas.trip import TripRequest
from app.llm.client import LLMClient
from app.llm.prompts import EXPLAINER_SYSTEM_PROMPT

class DayExplanation(BaseModel):
    day: int
    explanation: str

class ExplanationOutput(BaseModel):
    trip_summary: str
    why_this_fits: str
    day_explanations: List[DayExplanation]

class LLMExplainer:
    @staticmethod
    def generate_explanation(request: TripRequest, response: TripResponse) -> Optional[AIExplanation]:
        client = LLMClient.get_instance()
        
        # Prepare context for the LLM
        context = f"""
        User Request:
        Traveller Type: {request.travellers.type.value} ({request.travellers.adults} adults, {len(request.travellers.children)} children)
        Pace: {request.pace.value}
        Budget: {request.budget.value}
        
        Generated Itinerary:
        Total Cost: {response.summary.estimated_cost} INR
        Validation Passed: {response.validation.passed}
        """
        
        for day in response.days:
            context += f"Day {day.day} ({day.theme}):\n"
            for act in day.activities:
                context += f"- {act.name} ({act.category}, {act.start_time}-{act.end_time})\n"
                
        # Generate structured explanation
        generated = client.generate_structured(
            system_instruction=EXPLAINER_SYSTEM_PROMPT,
            prompt=context,
            schema=ExplanationOutput
        )
        if generated is None:
            return None
        return AIExplanation(
            trip_summary=generated.trip_summary,
            why_this_fits=generated.why_this_fits,
            day_explanations={
                item.day: item.explanation for item in generated.day_explanations
            },
        )
