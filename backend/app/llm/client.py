import os
import logging
from typing import Optional, Type, TypeVar, Any
from google import genai
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def _safe_gemini_failure_reason(error: Exception) -> str:
    if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower():
        return "request_timeout"
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status_code in (401, "401"):
        return "invalid_api_key"
    if status_code in (403, "403"):
        return "api_permission_denied"
    if status_code in (404, "404"):
        return "model_or_endpoint_not_found"
    if status_code in (429, "429"):
        return "rate_limited"
    if isinstance(status_code, int) and status_code >= 500:
        return "gemini_service_error"
    return f"request_error:{type(error).__name__}"


class LLMClient:
    _instance: Optional['LLMClient'] = None
    
    def __init__(self):
        self.model = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        self.initialization_failure_reason = "missing_api_key"
        configured_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.api_key = (
            configured_key
            if configured_key and configured_key.lower() not in {
                "your_api_key_here",
                "replace_me",
                "changeme",
            }
            else None
        )
        if not self.api_key:
            self.client = None
            logger.info("GEMINI configured: false")
            logger.info("GEMINI model: %s", self.model)
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.initialization_failure_reason = ""
                logger.info("GEMINI configured: true")
                logger.info("GEMINI model: %s", self.model)
            except Exception as exc:
                self.initialization_failure_reason = (
                    f"client_initialization:{type(exc).__name__}"
                )
                logger.error(
                    "Gemini client initialization failed; fallback reason=%s",
                    self.initialization_failure_reason,
                )
                self.client = None
            
    @classmethod
    def get_instance(cls) -> 'LLMClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def generate_structured(self, system_instruction: str, prompt: str, schema: Type[T]) -> Optional[T]:
        if not self.client:
            return None
            
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2
                ),
            )
            # Response.parsed automatically maps if supported, otherwise parse json manually
            if hasattr(response, 'parsed') and response.parsed:
                if isinstance(response.parsed, dict):
                    return schema(**response.parsed)
                return response.parsed
                
            import json
            data = json.loads(response.text)
            return schema(**data)
        except Exception as exc:
            logger.error(
                "Structured Gemini generation failed; reason=%s",
                _safe_gemini_failure_reason(exc),
            )
            return None

    def generate_text(self, system_instruction: str, prompt: str) -> Optional[str]:
        if not self.client:
            logger.warning(
                "CHAT fallback reason=%s",
                self.initialization_failure_reason or "gemini_client_unavailable",
            )
            return None
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=700,
                ),
            )
            text = response.text
            if not text or not text.strip():
                logger.warning("CHAT fallback reason=empty_gemini_response")
                return None
            logger.info("CHAT provider=gemini model=%s", self.model)
            return text.strip()
        except Exception as exc:
            logger.error(
                "CHAT fallback reason=%s",
                _safe_gemini_failure_reason(exc),
            )
            return None
