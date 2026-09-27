from typing import List, Tuple
from app.models.place import Place
from app.schemas.trip import TripRequest
from app.planner.tracer import PlannerTracer

class ScoringEngine:
    def __init__(self, tracer: PlannerTracer):
        self.tracer = tracer

    def score_candidates(self, request: TripRequest, candidates: List[Place]) -> List[Tuple[Place, float]]:
        scored_candidates = []

        for place in candidates:
            score = 0.0
            
            # 1. Interest Match
            for interest in (place.interests or []):
                if interest in request.interests:
                    score += request.interests[interest]
                    
            # 2. Budget Match
            # simple heuristic: penalty if budget is tight and cost is high
            if request.budget.value == "budget" and place.estimated_cost > 1000:
                score -= 1.0
            elif request.budget.value == "luxury" and place.estimated_cost < 200:
                # luxury seekers might prefer premium experiences, slight penalty for very cheap unless highly rated
                score -= 0.2
                
            # 3. Base confidence
            score += (place.confidence or 0.0)

            scored_candidates.append((place, score))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        self.tracer.add_trace(
            stage="Scoring",
            action="Rank candidates",
            details=f"Top 3 candidates: {[(p.name, round(s, 2)) for p, s in scored_candidates[:3]]}"
        )
        return scored_candidates
