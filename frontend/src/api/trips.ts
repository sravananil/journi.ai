import type { ChatResponse, NearbyRecommendation, TripRequest, TripResponse } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "string";
}

function isOptionalNumber(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "number";
}

function isNearbyRecommendation(value: unknown): value is NearbyRecommendation {
  return (
    isRecord(value) &&
    typeof value.place_id === "string" &&
    typeof value.name === "string" &&
    isOptionalString(value.category) &&
    typeof value.distance_km === "number" &&
    typeof value.travel_minutes === "number" &&
    typeof value.reason === "string" &&
    isOptionalString(value.source) &&
    ["FACT", "DERIVED", "UNKNOWN"].includes(String(value.place_evidence)) &&
    ["FACT", "DERIVED", "UNKNOWN"].includes(String(value.distance_evidence))
  );
}

function isJourney(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    (isRecord(value) &&
      typeof value.transport === "string" &&
      typeof value.status === "string" &&
      isOptionalString(value.departure_at) &&
      isOptionalString(value.arrival_at) &&
      isOptionalNumber(value.duration_minutes))
  );
}

function isTripResponse(value: unknown): value is TripResponse {
  if (!isRecord(value) || !isRecord(value.trip) || !isRecord(value.summary)) return false;
  if (!Array.isArray(value.days) || !Array.isArray(value.assumptions) || !Array.isArray(value.evidence)) return false;
  if (!Array.isArray(value.meal_suggestions) || !isRecord(value.validation)) return false;
  const checks = value.validation.checks;
  const checksValid =
    checks === undefined ||
    checks === null ||
    (isRecord(checks) &&
      ["dates", "schedule", "opening_hours", "geography", "budget", "traveller_suitability", "duplicates"].every(
        (check) => typeof checks[check] === "boolean",
      ));
  const explanation = value.ai_explanation;
  const explanationValid =
    explanation === undefined ||
    explanation === null ||
    (isRecord(explanation) &&
      typeof explanation.trip_summary === "string" &&
      typeof explanation.why_this_fits === "string" &&
      isRecord(explanation.day_explanations) &&
      Object.values(explanation.day_explanations).every((item) => typeof item === "string"));

  return (
    typeof value.trip.destination === "string" &&
    typeof value.trip.start_date === "string" &&
    typeof value.trip.end_date === "string" &&
    typeof value.trip.nights === "number" &&
    typeof value.summary.estimated_cost === "number" &&
    typeof value.summary.major_activities === "number" &&
    typeof value.summary.estimated_travel_time === "number" &&
    typeof value.summary.meal_cost === "number" &&
    typeof value.summary.estimated_known_total === "number" &&
    typeof value.validation.passed === "boolean" &&
    isJourney(value.journey) &&
    checksValid &&
    explanationValid &&
    value.assumptions.every((item) => typeof item === "string") &&
    value.evidence.every(
      (item) =>
        isRecord(item) &&
        typeof item.label === "string" &&
        ["FACT", "DERIVED", "UNKNOWN"].includes(String(item.value)) &&
        isOptionalString(item.source) &&
        isOptionalString(item.notes),
    ) &&
    value.meal_suggestions.every(
      (item) =>
        isRecord(item) &&
        typeof item.meal === "string" &&
        typeof item.restaurant === "string" &&
        typeof item.source === "string" &&
        isOptionalString(item.cuisine) &&
        isOptionalNumber(item.price) &&
        isOptionalNumber(item.rating) &&
        typeof item.day === "number" &&
        isOptionalString(item.start_time) &&
        isOptionalString(item.end_time) &&
        isOptionalNumber(item.lat) &&
        isOptionalNumber(item.lng) &&
        typeof item.scheduled === "boolean",
    ) &&
    value.days.every(
      (day) =>
        isRecord(day) &&
        typeof day.day === "number" &&
        typeof day.date === "string" &&
        typeof day.theme === "string" &&
        typeof day.limited_activities === "boolean" &&
        Array.isArray(day.recommendations) &&
        day.recommendations.every(isNearbyRecommendation) &&
        Array.isArray(day.activities) &&
        day.activities.every(
          (activity) =>
            isRecord(activity) &&
            typeof activity.place_id === "string" &&
            typeof activity.name === "string" &&
            typeof activity.start_time === "string" &&
            typeof activity.end_time === "string" &&
            typeof activity.duration_minutes === "number" &&
            typeof activity.estimated_cost === "number" &&
            typeof activity.travel_minutes === "number" &&
            typeof activity.reason === "string" &&
            isOptionalString(activity.category) &&
            isOptionalString(activity.image_url) &&
            isOptionalNumber(activity.lat) &&
            isOptionalNumber(activity.lng) &&
            isOptionalString(activity.source),
        ),
    )
  );
}

async function postJson(path: string, body: unknown): Promise<TripResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("We couldn't reach the JOURNI planning service. Check that the backend is running and try again.");
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : null;
    if (response.status === 422) {
      throw new ApiError(detail ?? "Some trip details are invalid. Review the form and try again.", response.status);
    }
    if (response.status >= 500) {
      throw new ApiError("The planning service encountered an error. Your trip details are unchanged; please try again.", response.status);
    }
    throw new ApiError(detail ?? "The planning service couldn't complete this request. Please try again.", response.status);
  }
  if (!payload || !isTripResponse(payload)) {
    throw new ApiError("The planning service returned an unexpected response. Please try again.");
  }
  return payload;
}

export function planTrip(request: TripRequest): Promise<TripResponse> {
  return postJson("/api/trips/plan", request);
}

export function refineTrip(originalRequest: TripRequest, refinementPrompt: string): Promise<TripResponse> {
  return postJson("/api/trips/refine", {
    original_request: originalRequest,
    refinement_prompt: refinementPrompt,
  });
}

export function addRecommendation(
  request: TripRequest,
  itinerary: TripResponse,
  day: number,
  placeId: string,
): Promise<TripResponse> {
  return postJson("/api/trips/recommendations/add", {
    request,
    itinerary,
    day,
    place_id: placeId,
  });
}

export async function askTrip(
  request: TripRequest,
  itinerary: TripResponse,
  question: string,
  currentDay: number,
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/trips/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        request,
        itinerary,
        question,
        current_day: currentDay,
      }),
    });
  } catch {
    throw new ApiError("We couldn't reach JOURNI. Check that the backend is running and try again.");
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : null;
    throw new ApiError(detail ?? "JOURNI couldn't answer about this itinerary. Please try again.", response.status);
  }
  if (
    !isRecord(payload) ||
    typeof payload.answer !== "string" ||
    typeof payload.requires_refinement !== "boolean" ||
    (payload.provider !== "gemini" && payload.provider !== "fallback") ||
    !Array.isArray(payload.recommendations) ||
    !payload.recommendations.every(isNearbyRecommendation)
  ) {
    throw new ApiError("JOURNI returned an unexpected chat response.");
  }
  return {
    answer: payload.answer,
    requires_refinement: payload.requires_refinement,
    recommendations: payload.recommendations,
    provider: payload.provider,
  };
}
