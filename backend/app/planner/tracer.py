from typing import Any, Dict, List
import json

class PlannerTracer:
    def __init__(self):
        self.traces: List[Dict[str, Any]] = []

    def add_trace(self, stage: str, action: str, details: Any):
        self.traces.append({
            "stage": stage,
            "action": action,
            "details": details
        })

    def get_traces(self) -> List[Dict[str, Any]]:
        return self.traces

    def dump(self):
        for trace in self.traces:
            print(f"[{trace['stage']}] {trace['action']}: {trace['details']}")
