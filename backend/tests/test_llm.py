import pytest
from types import SimpleNamespace
from app.llm.client import LLMClient
from app.llm.explainer import LLMExplainer
from app.llm.refiner import LLMRefiner
from app.schemas.response import TripResponse, TripInfo, TripSummary, ValidationResult, ValidationChecks
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, WalkingTolerance
from datetime import date, time

def test_llm_client_fallback_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Force re-initialization
    LLMClient._instance = None
    client = LLMClient.get_instance()
    
    assert client.client is None
    
    # generate_structured should gracefully return None
    class DummySchema:
        pass
        
    result = client.generate_structured("sys", "prompt", DummySchema)
    assert result is None

def test_llm_client_rejects_environment_placeholder(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")
    LLMClient._instance = None

    client = LLMClient.get_instance()

    assert client.client is None


def test_llm_client_uses_configured_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-test-model")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    LLMClient._instance = None

    client = LLMClient.get_instance()

    assert client.model == "gemini-test-model"


def test_gemini_request_failure_logs_safe_reason_and_returns_fallback(caplog):
    class UnauthorizedError(Exception):
        status_code = 401

    def fail_request(**_kwargs):
        raise UnauthorizedError("do-not-log-this-credential")

    client = LLMClient.__new__(LLMClient)
    client.client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fail_request)
    )
    client.model = "gemini-test-model"

    assert client.generate_text("system", "prompt") is None
    assert "CHAT fallback reason=invalid_api_key" in caplog.text
    assert "do-not-log-this-credential" not in caplog.text

def test_explainer_fallback_does_not_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    LLMClient._instance = None
    
    req = TripRequest(
        origin=Location(city="A", country="B", lat=0, lng=0),
        destination=Location(city="C", country="D", lat=0, lng=0),
        dates=Dates(start=date(2026,1,1), end=date(2026,1,5), nights=4),
        arrival="morning",
        departure="evening",
        travellers=Travellers(type="solo", adults=1),
        interests={"food": 1.0},
        pace=Pace.BALANCED,
        transport=Transport.TAXI,
        budget=Budget.MODERATE,
        walking_tolerance=WalkingTolerance.MODERATE,
        day_start=time(9, 0)
    )
    
    resp = TripResponse(
        trip=TripInfo(destination="C", start_date=date(2026,1,1), end_date=date(2026,1,5), nights=4),
        days=[],
        summary=TripSummary(estimated_cost=0, major_activities=0, estimated_travel_time=0),
        assumptions=[],
        validation=ValidationResult(passed=True, checks=ValidationChecks(dates=True, schedule=True, opening_hours=True, geography=True, budget=True, traveller_suitability=True, duplicates=True))
    )
    
    # Should not raise exception
    explanation = LLMExplainer.generate_explanation(req, resp)
    assert explanation is None
