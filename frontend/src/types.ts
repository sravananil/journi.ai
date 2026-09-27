export type Location = {
  city: string;
  country: string;
  lat: number;
  lng: number;
};

export type JourneyTransport =
  | "train"
  | "bus"
  | "car"
  | "taxi"
  | "public transport"
  | "scooter/bike"
  | "walking + public transport"
  | "no preference";

export type JourneyStatus = "confirmed" | "not_booked" | "planned";

export type JourneyRequest = {
  transport: JourneyTransport;
  status: JourneyStatus;
  departure_at?: string;
  arrival_at?: string;
};

export type TripRequest = {
  origin: Location;
  destination: Location;
  dates: { start: string; end: string; nights: number };
  arrival: "morning" | "afternoon" | "evening" | "night";
  departure: "morning" | "afternoon" | "evening" | "night";
  travellers: {
    type: "solo" | "couple" | "family" | "friends" | "seniors";
    adults: number;
    children: number[];
    seniors: number;
  };
  interests: Record<string, number>;
  pace: "easy-going" | "balanced" | "packed";
  transport:
    | "car"
    | "taxi"
    | "public transport"
    | "scooter/bike"
    | "walking + public transport"
    | "no preference";
  budget: "budget" | "moderate" | "premium" | "luxury";
  dietary: string[];
  walking_tolerance: "low" | "moderate" | "high";
  avoid: string[];
  day_start: string;
  journey?: JourneyRequest | null;
};

export type EvidenceType = "FACT" | "DERIVED" | "UNKNOWN";

export type NearbyRecommendation = {
  place_id: string;
  name: string;
  category?: string | null;
  distance_km: number;
  travel_minutes: number;
  reason: string;
  source?: string | null;
  distance_evidence: EvidenceType;
  place_evidence: EvidenceType;
};

export type TripResponse = {
  trip: {
    destination: string;
    start_date: string;
    end_date: string;
    nights: number;
  };
  days: Array<{
    day: number;
    date: string;
    theme: string;
    limited_activities: boolean;
    recommendations: NearbyRecommendation[];
    activities: Array<{
      place_id: string;
      name: string;
      start_time: string;
      end_time: string;
      duration_minutes: number;
      category?: string | null;
      estimated_cost: number;
      travel_minutes: number;
      reason: string;
      image_url?: string | null;
      lat?: number | null;
      lng?: number | null;
      source?: string | null;
    }>;
  }>;
  summary: {
    estimated_cost: number;
    major_activities: number;
    estimated_travel_time: number;
    meal_cost: number;
    estimated_known_total: number;
  };
  assumptions: string[];
  evidence: Array<{
    label: string;
    value: EvidenceType;
    source?: string | null;
    notes?: string | null;
  }>;
  validation: {
    passed: boolean;
    checks?: {
      dates: boolean;
      schedule: boolean;
      opening_hours: boolean;
      geography: boolean;
      budget: boolean;
      traveller_suitability: boolean;
      duplicates: boolean;
    } | null;
  };
  ai_explanation?: {
    trip_summary: string;
    why_this_fits: string;
    day_explanations: Record<string, string>;
  } | null;
  meal_suggestions: Array<{
    meal: string;
    restaurant: string;
    cuisine?: string | null;
    price?: number | null;
    rating?: number | null;
    source: string;
    day: number;
    start_time?: string | null;
    end_time?: string | null;
    lat?: number | null;
    lng?: number | null;
    scheduled: boolean;
  }>;
  journey?: {
    transport: JourneyTransport;
    status: JourneyStatus;
    departure_at?: string | null;
    arrival_at?: string | null;
    duration_minutes?: number | null;
  } | null;
};

export type ChatResponse = {
  answer: string;
  requires_refinement: boolean;
  recommendations: NearbyRecommendation[];
  provider: "gemini" | "fallback";
};

export type LocationCatalog = {
  origins: Location[];
  destinations: Location[];
};
