from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.llm.client import LLMClient
from app.llm.prompts import REFINER_SYSTEM_PROMPT


class RefinementCommand(BaseModel):
    """Structured intent extracted from a user refinement request.
    
    Gemini maps natural language → one or more of these structured commands.
    The deterministic planner then executes the commands.
    Gemini must NOT generate the itinerary directly.
    """
    action: str = Field(description="The refinement action to perform")
    day: int = Field(default=0, description="Target day (0 = whole trip)")
    target_value: Optional[str] = Field(default=None, description="String value, e.g. pace name or category")
    days_delta: int = Field(
        default=0,
        description="Number of days to add (+) or remove (-). Only used for increase_trip_days / decrease_trip_days."
    )

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid_actions = {
            'reduce_day_density',
            'increase_day_density',
            'change_pace',
            'avoid_category',
            'increase_trip_days',
            'decrease_trip_days',
            'change_interest_focus',
        }
        if v not in valid_actions:
            raise ValueError(f"Unknown action '{v}'. Must be one of: {valid_actions}")
        return v

    @field_validator('days_delta')
    @classmethod
    def validate_days_delta(cls, v: int) -> int:
        # Bound to prevent absurd inputs. Max ±14 days per refinement.
        if abs(v) > 14:
            raise ValueError(f"days_delta {v} is out of safe range [-14, 14]")
        return v


class MultiRefinementCommand(BaseModel):
    """Multiple refinement intents from a single user request."""
    commands: List[RefinementCommand] = Field(
        description="List of structured refinement commands extracted from the user request"
    )


class LLMRefiner:
    @staticmethod
    def interpret(prompt: str) -> Optional[MultiRefinementCommand]:
        """
        Use Gemini to interpret a natural language refinement request into structured commands.
        Returns None if Gemini is unavailable or output is invalid.
        """
        client = LLMClient.get_instance()
        return client.generate_structured(
            system_instruction=REFINER_SYSTEM_PROMPT,
            prompt=f"User refinement request: {prompt}",
            schema=MultiRefinementCommand
        )
