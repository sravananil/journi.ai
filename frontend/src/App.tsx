import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { addRecommendation as addTripRecommendation, ApiError, askTrip, planTrip, refineTrip } from "./api/trips";
import { loadJourneyTicket, removeJourneyTicket, saveJourneyTicket } from "./api/journeyTicket";
import { LocationPicker } from "./components/LocationPicker";
import type { ChatResponse, JourneyStatus, JourneyTransport, Location, LocationCatalog, NearbyRecommendation, TripRequest, TripResponse } from "./types";
import "./app.css";
import "./journey.css";

type Screen = "home" | "planner" | "loading" | "itinerary" | "error";
type PlanError = { title: string; message: string };
const MapLibreView = lazy(() => import("./components/MapView").then((module) => ({ default: module.MapView })));

const INTERESTS = [
  ["culture", "Art & Culture", "palette"],
  ["food", "Food & Culinary", "restaurant"],
  ["beaches", "Beaches & Coast", "waves"],
  ["adventure", "Adventure", "hiking"],
  ["nature", "Nature & Outdoors", "landscape"],
  ["photography", "Photography", "photo_camera"],
  ["wellness", "Wellness", "spa"],
  ["shopping", "Shopping", "storefront"],
  ["sightseeing", "Sightseeing", "explore"],
] as const;
const TRAVELLER_TYPES = [
  ["solo", "Solo Explorer", "person", "Independent & flexible"],
  ["couple", "Couple", "favorite", "A shared getaway"],
  ["family", "Family", "family_restroom", "Travelling together"],
  ["friends", "Friends", "groups", "A trip with friends"],
  ["seniors", "Seniors", "elderly", "Comfortable pacing"],
] as const;
const PIPELINE = [
  "Understanding your preferences",
  "Finding relevant places",
  "Organizing a geographic route",
  "Scheduling your days",
  "Validating the itinerary",
];
const TODAY = (() => {
  const localDate = new Date();
  localDate.setMinutes(localDate.getMinutes() - localDate.getTimezoneOffset());
  return localDate.toISOString().slice(0, 10);
})();

function nightsBetween(start: string, end: string): number {
  if (!start || !end) return 0;
  return Math.round((Date.parse(`${end}T12:00:00`) - Date.parse(`${start}T12:00:00`)) / 86_400_000);
}

function toggleValue(values: string[], value: string, update: (next: string[]) => void) {
  update(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
}

function App() {
  const [catalog, setCatalog] = useState<LocationCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [screen, setScreen] = useState<Screen>("home");
  const [step, setStep] = useState(1);
  const [origin, setOrigin] = useState<Location | null>(null);
  const [destination, setDestination] = useState<Location | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [arrival, setArrival] = useState<TripRequest["arrival"]>("morning");
  const [departure, setDeparture] = useState<TripRequest["departure"]>("afternoon");
  const [journeyEnabled, setJourneyEnabled] = useState(false);
  const [journeyTimesEnabled, setJourneyTimesEnabled] = useState(false);
  const [journeyTransport, setJourneyTransport] = useState<JourneyTransport>("train");
  const [journeyStatus, setJourneyStatus] = useState<JourneyStatus>("not_booked");
  const [journeyDepartureAt, setJourneyDepartureAt] = useState("");
  const [journeyArrivalAt, setJourneyArrivalAt] = useState("");
  const [storedTicket, setStoredTicket] = useState<{ key: string; name: string; url: string } | null>(null);
  const [ticketIssue, setTicketIssue] = useState<{ key: string; message: string } | null>(null);
  const [travellerType, setTravellerType] = useState<TripRequest["travellers"]["type"] | "">("");
  const [adults, setAdults] = useState(1);
  const [childAges, setChildAges] = useState("");
  const [seniors, setSeniors] = useState(0);
  const [interests, setInterests] = useState<string[]>([]);
  const [pace, setPace] = useState<TripRequest["pace"] | "">("");
  const [walkingTolerance, setWalkingTolerance] = useState<TripRequest["walking_tolerance"]>("moderate");
  const [budget, setBudget] = useState<TripRequest["budget"] | "">("");
  const [transport, setTransport] = useState<TripRequest["transport"]>("walking + public transport");
  const [dayStart, setDayStart] = useState("09:00");
  const [dietary, setDietary] = useState<string[]>([]);
  const [avoidLateNights, setAvoidLateNights] = useState(false);
  const [tripRequest, setTripRequest] = useState<TripRequest | null>(null);
  const [itinerary, setItinerary] = useState<TripResponse | null>(null);
  const [error, setError] = useState<PlanError | null>(null);
  const [formError, setFormError] = useState("");
  const [activeDay, setActiveDay] = useState(0);
  const [view, setView] = useState<"timeline" | "map">("timeline");
  const [refinement, setRefinement] = useState("");
  const [refining, setRefining] = useState(false);
  const [refinementError, setRefinementError] = useState("");
  const [addingRecommendation, setAddingRecommendation] = useState("");
  const itineraryRequestVersion = useRef(0);

  useEffect(() => {
    fetch("/locations.json")
      .then((response) => {
        if (!response.ok) throw new Error("City data is unavailable.");
        return response.json() as Promise<LocationCatalog>;
      })
      .then(setCatalog)
      .catch(() => setCatalogError("We couldn't load the supported city list. Refresh to try again."));
  }, []);

  const ticketStorageKey = origin && destination && startDate
    ? `${origin.city}|${destination.city}|${startDate}`
    : "";
  const ticketName = storedTicket?.key === ticketStorageKey ? storedTicket.name : "";
  const ticketUrl = storedTicket?.key === ticketStorageKey ? storedTicket.url : "";
  const ticketError = ticketIssue?.key === ticketStorageKey ? ticketIssue.message : "";

  function reportTicketError(message: string) {
    setTicketIssue(message ? { key: ticketStorageKey, message } : null);
  }

  useEffect(() => {
    if (!ticketUrl) return;
    return () => URL.revokeObjectURL(ticketUrl);
  }, [ticketUrl]);

  useEffect(() => {
    if (!ticketStorageKey) return;
    let cancelled = false;
    void loadJourneyTicket(ticketStorageKey)
      .then((ticket) => {
        if (!cancelled) {
          setStoredTicket(ticket ? {
            key: ticketStorageKey,
            name: ticket.name,
            url: URL.createObjectURL(ticket),
          } : null);
          setTicketIssue(null);
        }
      })
      .catch(() => {
        if (!cancelled) setTicketIssue({ key: ticketStorageKey, message: "The locally saved ticket could not be read." });
      });
    return () => { cancelled = true; };
  }, [ticketStorageKey]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [screen]);

  const nights = nightsBetween(startDate, endDate);
  const tripSummary = useMemo(() => {
    if (!itinerary) return "";
    return `${itinerary.trip.nights} ${itinerary.trip.nights === 1 ? "Night" : "Nights"} · ${itinerary.days.length} itinerary ${itinerary.days.length === 1 ? "day" : "days"} · ${itinerary.trip.destination}`;
  }, [itinerary]);

  function validateStep(current: number): string {
    if (current === 1 && (!origin || !destination)) return "Choose an origin and destination from the JOURNI location list.";
    if (current === 1 && origin?.city === destination?.city) return "Origin and destination need to be different cities.";
    if (current === 2 && (!startDate || !endDate || nights < 1)) return "Choose valid start and end dates at least one night apart.";
    if (current === 2 && journeyEnabled) {
      const timesRequired = journeyStatus === "confirmed" || journeyStatus === "planned";
      if ((journeyTimesEnabled || timesRequired) && (!journeyDepartureAt || !journeyArrivalAt)) return "Enter both the expected departure and arrival date and time.";
      if (Boolean(journeyDepartureAt) !== Boolean(journeyArrivalAt)) return "Enter both journey times, or leave both blank.";
      if (journeyDepartureAt && journeyArrivalAt && Date.parse(journeyArrivalAt) <= Date.parse(journeyDepartureAt)) return "Journey arrival must be after departure.";
      if (journeyArrivalAt && journeyArrivalAt.slice(0, 10) > startDate) return "Journey arrival must be on or before the selected itinerary start date.";
    }
    if (current === 3 && (!travellerType || adults < 1 || adults > 20 || seniors < 0 || seniors > 20)) return "Choose a traveller type and enter a valid party size.";
    if (current === 3 && childAges.trim() && childAges.split(",").some((age) => !/^\s*\d{1,2}\s*$/.test(age) || Number(age) > 17)) return "Enter child ages as comma-separated numbers from 0 to 17.";
    if (current === 4 && interests.length === 0) return "Choose at least one interest to personalize your itinerary.";
    if (current === 5 && !pace) return "Choose your preferred travel pace.";
    if (current === 6 && !budget) return "Choose a budget range.";
    return "";
  }

  function nextStep() {
    const message = validateStep(step);
    if (message) {
      setFormError(message);
      return;
    }
    setFormError("");
    setStep((current) => Math.min(7, current + 1));
  }

  function previousStep() {
    setFormError("");
    setStep((current) => Math.max(1, current - 1));
  }

  async function submitPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step !== 7) {
      setFormError("Complete the final requirements step before generating your itinerary.");
      return;
    }
    const firstInvalid = [1, 2, 3, 4, 5, 6, 7].find((index) => validateStep(index));
    if (firstInvalid) {
      setStep(firstInvalid);
      setFormError(validateStep(firstInvalid));
      return;
    }
    if (!origin || !destination || !pace || !budget || !travellerType) return;

    const request: TripRequest = {
      origin,
      destination,
      dates: { start: startDate, end: endDate, nights },
      arrival,
      departure,
      travellers: {
        type: travellerType,
        adults,
        children: childAges.trim() ? childAges.split(",").map((age) => Number(age.trim())) : [],
        seniors,
      },
      interests: Object.fromEntries(interests.map((interest) => [interest, 1])),
      pace,
      transport,
      budget,
      dietary,
      walking_tolerance: walkingTolerance,
      avoid: avoidLateNights ? ["late_nights"] : [],
      day_start: dayStart,
      journey: journeyEnabled ? {
        transport: journeyTransport,
        status: journeyStatus,
        departure_at: journeyTimesEnabled || journeyStatus === "confirmed" || journeyStatus === "planned" ? journeyDepartureAt : undefined,
        arrival_at: journeyTimesEnabled || journeyStatus === "confirmed" || journeyStatus === "planned" ? journeyArrivalAt : undefined,
      } : null,
    };

    setTripRequest(request);
    await executePlan(request);
  }

  async function executePlan(request: TripRequest) {
    setScreen("loading");
    setError(null);
    try {
      const result = await planTrip(request);
      if (result.days.length === 0 || result.summary.major_activities === 0) {
        setError({
          title: "No itinerary could be assembled",
          message: "The planner didn't find enough suitable places for this destination and set of preferences. Try another supported destination or adjust your trip preferences.",
        });
        setScreen("error");
        return;
      }
      setItinerary(result);
      setActiveDay(0);
      setView("timeline");
      setScreen("itinerary");
    } catch (cause) {
      setError({
        title: "We couldn't generate this itinerary",
        message: cause instanceof ApiError ? cause.message : "Something went wrong while planning. Please review your trip and try again.",
      });
      setScreen("error");
    }
  }

  async function submitRefinement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tripRequest || !refinement.trim() || refining) return;
    await executeRefinement();
  }

  async function executeRefinement() {
    if (!tripRequest || !refinement.trim()) return;
    const requestVersion = itineraryRequestVersion.current;
    setRefining(true);
    setRefinementError("");
    try {
      const updated = await refineTrip(tripRequest, refinement.trim());
      if (requestVersion !== itineraryRequestVersion.current) return;
      if (!updated.days.length || !updated.summary.major_activities) {
        throw new ApiError("The planner couldn't produce an updated itinerary for that request.");
      }
      setItinerary(updated);
      setActiveDay(0);
      setRefinement("");
    } catch (cause) {
      if (requestVersion !== itineraryRequestVersion.current) return;
      setRefinementError(cause instanceof ApiError ? cause.message : "Please try that refinement again.");
    } finally {
      if (requestVersion === itineraryRequestVersion.current) setRefining(false);
    }
  }

  async function retryRefinement() {
    if (refining) return;
    await executeRefinement();
  }

  async function askAboutTrip(question: string, currentDay: number): Promise<ChatResponse> {
    if (!tripRequest || !itinerary) throw new ApiError("Generate an itinerary before asking about your trip.");
    return askTrip(tripRequest, itinerary, question, currentDay);
  }

  async function addRecommendation(day: number, recommendation: NearbyRecommendation) {
    if (!tripRequest || !itinerary || addingRecommendation) return;
    const requestVersion = itineraryRequestVersion.current;
    setAddingRecommendation(recommendation.place_id);
    try {
      const updated = await addTripRecommendation(tripRequest, itinerary, day, recommendation.place_id);
      if (requestVersion !== itineraryRequestVersion.current) return;
      setItinerary(updated);
      const selectedIndex = updated.days.findIndex((item) => item.day === day);
      if (selectedIndex >= 0) setActiveDay(selectedIndex);
    } finally {
      if (requestVersion === itineraryRequestVersion.current) setAddingRecommendation("");
    }
  }

  async function attachJourneyTicket(file: File | null) {
    if (!file) return;
    if (!ticketStorageKey) {
      reportTicketError("Choose the origin, destination, and trip start date before attaching a ticket.");
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase();
    const allowedTypes = ["application/pdf", "image/png", "image/jpeg"];
    if (!allowedTypes.includes(file.type) && !["pdf", "png", "jpg", "jpeg"].includes(extension ?? "")) {
      reportTicketError("Choose a PDF, PNG, JPG, or JPEG ticket document.");
      return;
    }
    try {
      await saveJourneyTicket(file, ticketStorageKey);
      setStoredTicket({
        key: ticketStorageKey,
        name: file.name,
        url: URL.createObjectURL(file),
      });
      reportTicketError("");
    } catch {
      reportTicketError("The ticket could not be stored in this browser. Check local storage space and try again.");
    }
  }

  async function clearJourneyTicket() {
    if (!ticketStorageKey) return;
    try {
      await removeJourneyTicket(ticketStorageKey);
      setStoredTicket(null);
      reportTicketError("");
    } catch {
      reportTicketError("The locally stored ticket could not be removed.");
    }
  }

  const showPlanner = () => {
    setFormError("");
    setScreen("planner");
  };

  function startNewTrip() {
    itineraryRequestVersion.current += 1;
    setStep(1);
    setOrigin(null);
    setDestination(null);
    setStartDate("");
    setEndDate("");
    setArrival("morning");
    setDeparture("afternoon");
    setJourneyEnabled(false);
    setJourneyTimesEnabled(false);
    setJourneyTransport("train");
    setJourneyStatus("not_booked");
    setJourneyDepartureAt("");
    setJourneyArrivalAt("");
    setStoredTicket(null);
    setTicketIssue(null);
    setTravellerType("");
    setAdults(1);
    setChildAges("");
    setSeniors(0);
    setInterests([]);
    setPace("");
    setWalkingTolerance("moderate");
    setBudget("");
    setTransport("walking + public transport");
    setDayStart("09:00");
    setDietary([]);
    setAvoidLateNights(false);
    setTripRequest(null);
    setItinerary(null);
    setError(null);
    setFormError("");
    setActiveDay(0);
    setView("timeline");
    setRefinement("");
    setRefining(false);
    setRefinementError("");
    setAddingRecommendation("");
    setScreen("planner");
  }

  return (
    <div className="app-shell">
      <Header screen={screen} onHome={() => setScreen("home")} onPlanner={showPlanner} onItinerary={() => itinerary && setScreen("itinerary")} />
      {screen === "home" && <Home onPlan={showPlanner} />}
      {screen === "planner" && (
        <Planner
          catalog={catalog}
          catalogError={catalogError}
          origin={origin}
          destination={destination}
          setOrigin={setOrigin}
          setDestination={setDestination}
          startDate={startDate}
          endDate={endDate}
          setStartDate={(value) => { setStartDate(value); if (endDate && value >= endDate) setEndDate(""); }}
          setEndDate={setEndDate}
          nights={nights}
          arrival={arrival}
          setArrival={setArrival}
          departure={departure}
          setDeparture={setDeparture}
          journeyEnabled={journeyEnabled}
          setJourneyEnabled={setJourneyEnabled}
          journeyTimesEnabled={journeyTimesEnabled}
          setJourneyTimesEnabled={setJourneyTimesEnabled}
          journeyTransport={journeyTransport}
          setJourneyTransport={setJourneyTransport}
          journeyStatus={journeyStatus}
          setJourneyStatus={setJourneyStatus}
          journeyDepartureAt={journeyDepartureAt}
          setJourneyDepartureAt={setJourneyDepartureAt}
          journeyArrivalAt={journeyArrivalAt}
          setJourneyArrivalAt={setJourneyArrivalAt}
          ticketName={ticketName}
          ticketError={ticketError}
          onTicketFile={attachJourneyTicket}
          onClearTicket={clearJourneyTicket}
          travellerType={travellerType}
          setTravellerType={setTravellerType}
          adults={adults}
          setAdults={setAdults}
          childAges={childAges}
          setChildAges={setChildAges}
          seniors={seniors}
          setSeniors={setSeniors}
          interests={interests}
          setInterests={setInterests}
          pace={pace}
          setPace={setPace}
          walkingTolerance={walkingTolerance}
          setWalkingTolerance={setWalkingTolerance}
          budget={budget}
          setBudget={setBudget}
          transport={transport}
          setTransport={setTransport}
          dayStart={dayStart}
          setDayStart={setDayStart}
          dietary={dietary}
          setDietary={setDietary}
          avoidLateNights={avoidLateNights}
          setAvoidLateNights={setAvoidLateNights}
          step={step}
          formError={formError}
          onNext={nextStep}
          onPrevious={previousStep}
          onGoToStep={setStep}
          onSubmit={submitPlan}
        />
      )}
      {screen === "loading" && <LoadingScreen destination={destination?.city ?? ""} />}
      {screen === "error" && error && <ErrorScreen error={error} onEdit={showPlanner} onRetry={() => { if (tripRequest) void executePlan(tripRequest); }} />}
      {screen === "itinerary" && itinerary && (
        <ItineraryDashboard
          response={itinerary}
          request={tripRequest}
          tripSummary={tripSummary}
          ticketName={ticketName}
          ticketUrl={ticketUrl}
          ticketError={ticketError}
          onTicketFile={attachJourneyTicket}
          onClearTicket={clearJourneyTicket}
          activeDay={activeDay}
          onSelectDay={setActiveDay}
          view={view}
          onView={setView}
          refinement={refinement}
          onRefinement={setRefinement}
          refining={refining}
          refinementError={refinementError}
          onRefine={submitRefinement}
          onRetryRefinement={retryRefinement}
          onNewTrip={startNewTrip}
          onAsk={askAboutTrip}
          onAddRecommendation={addRecommendation}
          addingRecommendation={addingRecommendation}
        />
      )}
      <Footer />
    </div>
  );
}

type HeaderProps = { screen: Screen; onHome: () => void; onPlanner: () => void; onItinerary: () => void };

function Header({ screen, onHome, onPlanner, onItinerary }: HeaderProps) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <button className="brand" onClick={onHome} aria-label="JOURNI home">
          <span className="brand-mark material-symbols-outlined">explore</span>
          <span>JOURNI</span>
        </button>
        <nav aria-label="Main navigation">
          <button className={screen === "home" ? "nav-link active" : "nav-link"} onClick={onHome}>Home</button>
          <button className={screen === "planner" ? "nav-link active" : "nav-link"} onClick={onPlanner}>Trip Planner</button>
          <button className={screen === "itinerary" ? "nav-link active" : "nav-link"} onClick={onItinerary} disabled={screen !== "itinerary"}>Itinerary</button>
        </nav>
        <button className="button button-primary header-cta" onClick={onPlanner}>
          <span className="material-symbols-outlined">add_location_alt</span> Plan a Trip
        </button>
      </div>
    </header>
  );
}

function Home({ onPlan }: { onPlan: () => void }) {
  return (
    <main className="home-page">
      <section className="hero">
        <div className="hero-orb orb-one" />
        <div className="hero-orb orb-two" />
        <div className="hero-content">
          <div className="eyebrow"><span className="material-symbols-outlined">auto_awesome</span> AI-assisted trip planning</div>
          <h1>Make every journey<br /><span>feel like yours.</span></h1>
          <p>Tell JOURNI what matters to you. Get a thoughtful, day-by-day itinerary shaped around your interests, pace, and practical constraints.</p>
          <button className="button button-primary button-large" onClick={onPlan}>
            Start planning <span className="material-symbols-outlined">arrow_forward</span>
          </button>
          <div className="hero-proof">
            <span className="material-symbols-outlined">route</span>
            Personalized preferences <i /> Deterministic planning <i /> Clear assumptions
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="art-sun" />
          <div className="art-hill hill-back" />
          <div className="art-hill hill-front" />
          <div className="art-card">
            <span className="art-card-kicker">YOUR NEXT JOURNEY</span>
            <strong>Find your own way.</strong>
            <div className="art-route"><span /><span /><span /><span /></div>
            <div className="art-card-foot"><span>Preferences first</span><span className="material-symbols-outlined">north_east</span></div>
          </div>
          <div className="floating-stamp"><span className="material-symbols-outlined">explore</span><small>Thoughtfully<br />planned</small></div>
        </div>
      </section>
      <section className="home-bottom">
        <div><span className="section-kicker">A better way to plan</span><h2>Good trips start with what matters to you.</h2></div>
        <div className="home-feature-grid">
          <Feature icon="tune" title="Your preferences" text="Interests, travel pace, budget, and traveller type guide the plan." />
          <Feature icon="route" title="A feasible route" text="Places are grouped geographically and scheduled with estimated travel time." />
          <Feature icon="fact_check" title="Honest details" text="Facts, derived estimates, and unknowns are clearly distinguished." />
        </div>
      </section>
    </main>
  );
}

function Feature({ icon, title, text }: { icon: string; title: string; text: string }) {
  return <article className="feature-card"><span className="feature-icon material-symbols-outlined">{icon}</span><h3>{title}</h3><p>{text}</p></article>;
}

type PlannerProps = {
  catalog: LocationCatalog | null;
  catalogError: string;
  origin: Location | null;
  destination: Location | null;
  setOrigin: (value: Location | null) => void;
  setDestination: (value: Location | null) => void;
  startDate: string;
  endDate: string;
  setStartDate: (value: string) => void;
  setEndDate: (value: string) => void;
  nights: number;
  arrival: TripRequest["arrival"];
  setArrival: (value: TripRequest["arrival"]) => void;
  departure: TripRequest["departure"];
  setDeparture: (value: TripRequest["departure"]) => void;
  journeyEnabled: boolean;
  setJourneyEnabled: (value: boolean) => void;
  journeyTimesEnabled: boolean;
  setJourneyTimesEnabled: (value: boolean) => void;
  journeyTransport: JourneyTransport;
  setJourneyTransport: (value: JourneyTransport) => void;
  journeyStatus: JourneyStatus;
  setJourneyStatus: (value: JourneyStatus) => void;
  journeyDepartureAt: string;
  setJourneyDepartureAt: (value: string) => void;
  journeyArrivalAt: string;
  setJourneyArrivalAt: (value: string) => void;
  ticketName: string;
  ticketError: string;
  onTicketFile: (file: File | null) => void;
  onClearTicket: () => void;
  travellerType: TripRequest["travellers"]["type"] | "";
  setTravellerType: (value: TripRequest["travellers"]["type"] | "") => void;
  adults: number;
  setAdults: (value: number) => void;
  childAges: string;
  setChildAges: (value: string) => void;
  seniors: number;
  setSeniors: (value: number) => void;
  interests: string[];
  setInterests: (value: string[]) => void;
  pace: TripRequest["pace"] | "";
  setPace: (value: TripRequest["pace"] | "") => void;
  walkingTolerance: TripRequest["walking_tolerance"];
  setWalkingTolerance: (value: TripRequest["walking_tolerance"]) => void;
  budget: TripRequest["budget"] | "";
  setBudget: (value: TripRequest["budget"] | "") => void;
  transport: TripRequest["transport"];
  setTransport: (value: TripRequest["transport"]) => void;
  dayStart: string;
  setDayStart: (value: string) => void;
  dietary: string[];
  setDietary: (value: string[]) => void;
  avoidLateNights: boolean;
  setAvoidLateNights: (value: boolean) => void;
  step: number;
  formError: string;
  onNext: () => void;
  onPrevious: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onGoToStep: (step: number) => void;
};

function Planner(props: PlannerProps) {
  const { step } = props;
  const stepNames = ["Places", "Dates", "Travellers", "Interests", "Pace", "Budget", "Needs"];
  return (
    <main className="planner-page page-wrap">
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="material-symbols-outlined">auto_awesome</span> Personal trip planner</div>
          <h1>Plan your next journey</h1>
          <p>Share a few details and JOURNI will shape a route around your trip.</p>
        </div>
        <div className="step-display">Step <strong>{step}</strong> of 7<div className="progress-track"><span style={{ width: `${(step / 7) * 100}%` }} /></div></div>
      </div>
      {props.catalogError && <div className="notice error-notice">{props.catalogError}</div>}
      {!props.catalog && !props.catalogError ? <div className="loading-inline"><span className="spinner" /> Loading supported JOURNI locations…</div> : (
        <div className="planner-layout">
          <form className="planner-card" onSubmit={props.onSubmit} noValidate>
            <div className="step-tabs" aria-label="Planner steps">
              {stepNames.map((name, index) => (
                <button key={name} type="button" className={step === index + 1 ? "step-tab current" : step > index + 1 ? "step-tab complete" : "step-tab"} onClick={() => {
                  if (index + 1 < step) props.onGoToStep(index + 1);
                }} disabled={index + 1 > step}>
                  <span>{step > index + 1 ? "✓" : index + 1}</span><small>{name}</small>
                </button>
              ))}
            </div>
            <div className="planner-step-content">
              {step === 1 && <section>
                <StepHeading title="Where are you heading?" subtitle="Select from JOURNI's city data. Destinations are limited to places in the planner dataset." />
                <div className="form-grid two">
                  <LocationPicker label="Origin city" icon="flight_takeoff" value={props.origin} options={props.catalog?.origins ?? []} placeholder="Search an Indian city" onChange={props.setOrigin} />
                  <LocationPicker label="Destination" icon="location_on" value={props.destination} options={props.catalog?.destinations ?? []} placeholder="Search supported destinations" onChange={props.setDestination} />
                </div>
                <div className="inline-note"><span className="material-symbols-outlined">verified</span> Coordinates are taken from the existing JOURNI city dataset. No geocoding or guessed locations.</div>
              </section>}
              {step === 2 && <section>
                <StepHeading title="When are you travelling?" subtitle="Choose exact dates so the planner can schedule each itinerary day." />
                <div className="form-grid two">
                  <Field label="Start date"><input required type="date" min={TODAY} value={props.startDate} onChange={(event) => props.setStartDate(event.target.value)} /></Field>
                  <Field label="End date"><input required type="date" min={props.startDate || TODAY} value={props.endDate} onChange={(event) => props.setEndDate(event.target.value)} /></Field>
                </div>
                <div className="derived-date"><span className="material-symbols-outlined">calendar_month</span><span>Trip length</span><strong>{props.nights > 0 ? `${props.nights} ${props.nights === 1 ? "night" : "nights"}` : "Select your dates"}</strong><small>Calculated from your selected dates</small></div>
                <div className="form-grid two">
                  <Field label="Arrival time"><Select value={props.arrival} onChange={(value) => props.setArrival(value as TripRequest["arrival"])} options={["morning", "afternoon", "evening", "night"]} /></Field>
                  <Field label="Departure time"><Select value={props.departure} onChange={(value) => props.setDeparture(value as TripRequest["departure"])} options={["morning", "afternoon", "evening", "night"]} /></Field>
                </div>
                <section className="journey-form-panel">
                  <label className="toggle-row"><input type="checkbox" checked={props.journeyEnabled} onChange={(event) => props.setJourneyEnabled(event.target.checked)} /><span className="toggle-copy"><strong>Add outbound journey details</strong><small>Record your intercity transport and status. Exact times can constrain the first itinerary day.</small></span></label>
                  {props.journeyEnabled && <>
                    <div className="form-grid two">
                      <Field label="Intercity transport"><Select value={props.journeyTransport} onChange={(value) => {
                        const mode = value as JourneyTransport;
                        props.setJourneyTransport(mode);
                        const ownTransport = mode === "car" || mode === "scooter/bike";
                        props.setJourneyStatus(ownTransport ? "planned" : "not_booked");
                        if (ownTransport) props.setJourneyTimesEnabled(true);
                      }} options={["train", "bus", "taxi", "car", "public transport", "scooter/bike", "walking + public transport", "no preference"]} /></Field>
                      <Field label={props.journeyTransport === "car" || props.journeyTransport === "scooter/bike" ? "Journey status" : "Booking status"}><Select value={props.journeyStatus} onChange={(value) => {
                        const status = value as JourneyStatus;
                        props.setJourneyStatus(status);
                        if (status === "planned" || status === "confirmed") props.setJourneyTimesEnabled(true);
                      }} options={props.journeyTransport === "car" || props.journeyTransport === "scooter/bike" ? ["planned", "confirmed"] : ["confirmed", "not_booked"]} /></Field>
                    </div>
                    <label className="toggle-row journey-time-toggle"><input type="checkbox" checked={props.journeyTimesEnabled} onChange={(event) => props.setJourneyTimesEnabled(event.target.checked)} /><span className="toggle-copy"><strong>Enter expected departure and arrival times</strong><small>Required for confirmed journeys and planned own-transport trips.</small></span></label>
                    {props.journeyTimesEnabled && <div className="form-grid two">
                      <Field label="Departure date & time"><input type="datetime-local" value={props.journeyDepartureAt} onChange={(event) => props.setJourneyDepartureAt(event.target.value)} /></Field>
                      <Field label="Expected arrival date & time"><input type="datetime-local" value={props.journeyArrivalAt} onChange={(event) => props.setJourneyArrivalAt(event.target.value)} /></Field>
                    </div>}
                    <div className="ticket-upload-row">
                      <label className="ticket-file-label"><span className="material-symbols-outlined">attach_file</span>{props.ticketName || "Attach a ticket or journey document"}<input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(event) => void props.onTicketFile(event.target.files?.[0] ?? null)} /></label>
                      {props.ticketName && <button className="text-button" type="button" onClick={props.onClearTicket}>Remove</button>}
                    </div>
                    {props.ticketError && <p className="ticket-error" role="alert">{props.ticketError}</p>}
                    <small className="field-hint">The document stays in this browser only; it is not sent to JOURNI or treated as an official ticket.</small>
                  </>}
                </section>
              </section>}
              {step === 3 && <section>
                <StepHeading title="Who is travelling?" subtitle="Choose a traveller profile and give the planner the party size." />
                <div className="choice-grid traveller-grid">
                  {TRAVELLER_TYPES.map(([value, title, icon, text]) => <ChoiceCard key={value} selected={props.travellerType === value} icon={icon} title={title} text={text} onClick={() => props.setTravellerType(value)} />)}
                </div>
                <div className="form-grid three count-grid">
                  <Field label="Adults"><input type="number" min="1" max="20" value={props.adults} onChange={(event) => props.setAdults(Number(event.target.value))} /></Field>
                  <Field label="Children's ages"><input value={props.childAges} placeholder="e.g. 8, 12" onChange={(event) => props.setChildAges(event.target.value)} /><small className="field-hint">Separate ages with commas</small></Field>
                  <Field label="Seniors"><input type="number" min="0" max="20" value={props.seniors} onChange={(event) => props.setSeniors(Number(event.target.value))} /></Field>
                </div>
              </section>}
              {step === 4 && <section>
                <StepHeading title="What are your interests?" subtitle="Select all that appeal to your group. They will be sent as weighted planner preferences." />
                <div className="choice-grid interest-grid">
                  {INTERESTS.map(([value, title, icon]) => <ChoiceCard key={value} selected={props.interests.includes(value)} icon={icon} title={title} onClick={() => toggleValue(props.interests, value, props.setInterests)} compact />)}
                </div>
              </section>}
              {step === 5 && <section>
                <StepHeading title="Choose your travel pace" subtitle="How much would you like to fit into each day?" />
                <div className="stack-choice">
                  {([
                    ["easy-going", "Relaxed", "A lighter schedule with room to pause", "self_improvement"],
                    ["balanced", "Balanced", "A considered mix of activities and downtime", "balance"],
                    ["packed", "Packed", "Fit more stops into each day", "bolt"],
                  ] as const).map(([value, title, text, icon]) => <ChoiceCard key={value} selected={props.pace === value} icon={icon} title={title} text={text} onClick={() => props.setPace(value)} />)}
                </div>
                <Field label="Walking tolerance"><Select value={props.walkingTolerance} onChange={(value) => props.setWalkingTolerance(value as TripRequest["walking_tolerance"])} options={["low", "moderate", "high"]} /></Field>
              </section>}
              {step === 6 && <section>
                <StepHeading title="Budget & daily start" subtitle="Choose your budget range and preferred start time." />
                <div className="choice-grid budget-grid">
                  {([
                    ["budget", "Budget", "savings", "Keep costs in mind"],
                    ["moderate", "Moderate", "account_balance_wallet", "A balanced spend"],
                    ["premium", "Premium", "diamond", "More premium options"],
                    ["luxury", "Luxury", "hotel_class", "Prioritize luxury"],
                  ] as const).map(([value, title, icon, text]) => <ChoiceCard key={value} selected={props.budget === value} icon={icon} title={title} text={text} onClick={() => props.setBudget(value)} />)}
                </div>
                <div className="form-grid two">
                  <Field label="Preferred transport"><Select value={props.transport} onChange={(value) => props.setTransport(value as TripRequest["transport"])} options={["walking + public transport", "public transport", "car", "taxi", "scooter/bike", "no preference"]} /></Field>
                  <Field label="Preferred day start"><input type="time" value={props.dayStart} onChange={(event) => props.setDayStart(event.target.value)} /></Field>
                </div>
              </section>}
              {step === 7 && <section>
                <StepHeading title="Any special requirements?" subtitle="Share dietary requirements and constraints for the planner." />
                <div className="field"><label>Choose any that apply</label><div className="chip-row">
                  <button type="button" className={!props.dietary.length && !props.avoidLateNights ? "chip selected" : "chip"} aria-pressed={!props.dietary.length && !props.avoidLateNights} onClick={() => {
                    props.setDietary([]);
                    props.setAvoidLateNights(false);
                  }}>No special requirements</button>
                </div></div>
                <div className="field"><label>Dietary preferences</label><div className="chip-row">
                  {["vegetarian", "vegan", "gluten-free", "halal", "kosher"].map((value) => <button key={value} type="button" className={props.dietary.includes(value) ? "chip selected" : "chip"} onClick={() => toggleValue(props.dietary, value, props.setDietary)}>{value}</button>)}
                </div></div>
                <label className="toggle-row"><input type="checkbox" checked={props.avoidLateNights} onChange={(event) => props.setAvoidLateNights(event.target.checked)} /><span className="toggle-copy"><strong>Avoid late nights</strong><small>Exclude nightlife places where the planner supports this constraint.</small></span></label>
                <div className="inline-note"><span className="material-symbols-outlined">info</span> Accessibility and dietary data may be unavailable for some places. JOURNI will show unknown information rather than assume.</div>
              </section>}
              {props.formError && <div className="notice error-notice" role="alert"><span className="material-symbols-outlined">error</span>{props.formError}</div>}
            </div>
            <div className="wizard-actions">
              <button className="button button-soft" type="button" onClick={step === 1 ? () => window.scrollTo({ top: 0, behavior: "smooth" }) : props.onPrevious} disabled={step === 1}>
                <span className="material-symbols-outlined">arrow_back</span> Back
              </button>
              {step < 7 ? <button key="next-step" className="button button-primary" type="button" onClick={(event) => {
                event.preventDefault();
                props.onNext();
              }}>Next step <span className="material-symbols-outlined">arrow_forward</span></button> :
                <button key="submit-plan" className="button button-primary" type="submit">Generate itinerary <span className="material-symbols-outlined">auto_awesome</span></button>}
            </div>
          </form>
          <aside className="planner-summary">
            <div className="summary-head"><span className="material-symbols-outlined">fact_check</span><h2>Trip summary</h2><span className="summary-live">LIVE</span></div>
            <div className="summary-illustration"><div className="summary-land land-a" /><div className="summary-land land-b" /><span className="material-symbols-outlined">near_me</span><strong>{props.destination?.city ?? "Your destination"}</strong><small>India</small></div>
            <SummaryLine icon="flight_takeoff" title="From" value={props.origin?.city ?? "Choose a city"} />
            <SummaryLine icon="location_on" title="To" value={props.destination?.city ?? "Choose a destination"} />
            <SummaryLine icon="calendar_month" title="Dates" value={props.nights > 0 ? `${props.nights} nights` : "Choose your dates"} />
            <SummaryLine icon="groups" title="Travellers" value={props.travellerType || "Not selected"} />
            <SummaryLine icon="pace" title="Pace & budget" value={`${props.pace || "—"} · ${props.budget || "—"}`} />
            <div className="summary-foot"><span className="material-symbols-outlined">verified_user</span> Your preferences guide the plan. The deterministic planner builds the itinerary.</div>
          </aside>
        </div>
      )}
    </main>
  );
}

function StepHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="step-heading"><h2>{title}</h2><p>{subtitle}</p></div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span className="field-label">{label}</span>{children}</label>;
}

function Select({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return <select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((item) => <option value={item} key={item}>{item === "not_booked" ? "Not booked yet" : item.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase())}</option>)}</select>;
}

function ChoiceCard({ selected, icon, title, text, compact = false, onClick }: { selected: boolean; icon: string; title: string; text?: string; compact?: boolean; onClick: () => void }) {
  return <button type="button" className={`${compact ? "choice-card compact" : "choice-card"}${selected ? " chosen" : ""}`} aria-pressed={selected} onClick={onClick}>
    <span className="material-symbols-outlined choice-icon">{icon}</span><span className="choice-text"><strong>{title}</strong>{text && <small>{text}</small>}</span>{selected && <span className="material-symbols-outlined choice-check">check_circle</span>}
  </button>;
}

function SummaryLine({ icon, title, value }: { icon: string; title: string; value: string }) {
  return <div className="summary-line"><span className="material-symbols-outlined">{icon}</span><span>{title}</span><strong>{value}</strong></div>;
}

function LoadingScreen({ destination }: { destination: string }) {
  return (
    <main className="status-page page-wrap">
      <div className="loading-card">
        <div className="loading-top"><div className="loading-mark"><span className="spinner" /></div><div><div className="section-kicker">JOURNI planning engine</div><h1>Planning your journey</h1></div></div>
        <p className="loading-intro">Your trip details have been sent to the deterministic planner. This request may take a little while.</p>
        {destination && <div className="trip-context"><span className="material-symbols-outlined">travel_explore</span> Planning for <strong>{destination}</strong></div>}
        <div className="pipeline-list">{PIPELINE.map((label, index) => <div className="pipeline-item" key={label}><span className="pipeline-number">{index + 1}</span><span>{label}</span></div>)}</div>
        <div className="loading-disclaimer">The itinerary is built and validated by JOURNI's planning engine. Gemini may assist with language and explanations; it does not create the final itinerary.</div>
      </div>
    </main>
  );
}

function ErrorScreen({ error, onEdit, onRetry }: { error: PlanError; onEdit: () => void; onRetry: () => void }) {
  return (
    <main className="status-page page-wrap">
      <div className="error-card">
        <div className="status-icon"><span className="material-symbols-outlined">explore_off</span></div>
        <span className="section-kicker">Planning needs another look</span>
        <h1>{error.title}</h1>
        <p>{error.message}</p>
        <div className="error-details"><span className="material-symbols-outlined">info</span><div><strong>Your trip details are still here</strong><small>Try again or go back to edit your choices.</small></div></div>
        <div className="status-actions"><button className="button button-soft" onClick={onEdit}>Edit trip details</button><button className="button button-primary" onClick={onRetry}>Retry planning <span className="material-symbols-outlined">refresh</span></button></div>
      </div>
    </main>
  );
}

type DashboardProps = {
  response: TripResponse;
  request: TripRequest | null;
  tripSummary: string;
  ticketName: string;
  ticketUrl: string;
  ticketError: string;
  onTicketFile: (file: File | null) => void;
  onClearTicket: () => void;
  activeDay: number;
  onSelectDay: (day: number) => void;
  view: "timeline" | "map";
  onView: (view: "timeline" | "map") => void;
  refinement: string;
  onRefinement: (value: string) => void;
  refining: boolean;
  refinementError: string;
  onRefine: (event: FormEvent<HTMLFormElement>) => void;
  onRetryRefinement: () => void;
  onNewTrip: () => void;
  onAsk: (question: string, currentDay: number) => Promise<ChatResponse>;
  onAddRecommendation: (day: number, recommendation: NearbyRecommendation) => Promise<void>;
  addingRecommendation: string;
};

function ItineraryDashboard(props: DashboardProps) {
  const { response } = props;
  const days = response.days;
  const day = days[props.activeDay] ?? days[0];
  const tripDates = `${formatDate(response.trip.start_date)} – ${formatDate(response.trip.end_date)}`;
  return (
    <main className="dashboard-page">
      <div className="dashboard-top page-wrap">
        <div className="dashboard-trip-info">
          <div className="trip-badges"><span className="badge primary-badge"><span className="material-symbols-outlined">auto_awesome</span> JOURNI itinerary</span><span className="badge">{tripDates}</span><span className="badge">{response.trip.nights} nights</span>{props.request && <span className="badge">Selected budget: {props.request.budget}</span>}</div>
          <h1>{response.ai_explanation?.trip_summary || `${response.trip.destination} journey`}</h1>
          <p>{props.tripSummary}</p>
        </div>
        <div className="dashboard-actions">
          <div className="view-switch" role="group" aria-label="Itinerary view">
            <button className={props.view === "timeline" ? "selected" : ""} onClick={() => props.onView("timeline")}><span className="material-symbols-outlined">calendar_view_day</span> Timeline</button>
            <button className={props.view === "map" ? "selected" : ""} onClick={() => props.onView("map")}><span className="material-symbols-outlined">map</span> Map</button>
          </div>
          <button className="button button-soft" onClick={props.onNewTrip}><span className="material-symbols-outlined">add</span> New trip</button>
        </div>
      </div>
      {props.request && <JourneyStrip
        request={props.request}
        response={response}
        ticketName={props.ticketName}
        ticketUrl={props.ticketUrl}
        ticketError={props.ticketError}
        onTicketFile={props.onTicketFile}
        onClearTicket={props.onClearTicket}
      />}
      <div className="dashboard-grid page-wrap">
        <aside className="dashboard-sidebar">
          <section className="insight-card">
            <span className="material-symbols-outlined insight-icon">auto_awesome</span><div className="section-kicker">A note about your trip</div>
            <p>{response.ai_explanation?.why_this_fits ?? "Your day plans are grouped geographically and scheduled using your preferences."}</p>
            <div className={response.validation.passed ? "validation-pill passed" : "validation-pill review"}><span className="material-symbols-outlined">{response.validation.passed ? "verified" : "warning"}</span>{response.validation.passed ? "Planner validation passed" : "Some validation checks need attention"}</div>
          </section>
          {props.request && <AskJourniPanel
            key={day?.day ?? 0}
            day={day}
            onAsk={(question) => props.onAsk(question, day?.day ?? 1)}
            onAddRecommendation={props.onAddRecommendation}
            addingRecommendation={props.addingRecommendation}
          />}
          <section className="day-selector">
            <div className="sidebar-section-head"><h2>Your days</h2><span>{days.length}</span></div>
            {days.map((item, index) => <button key={`${item.day}-${item.date}`} onClick={() => props.onSelectDay(index)} className={props.activeDay === index ? "day-select active" : "day-select"}>
              <span className="day-number">{String(item.day).padStart(2, "0")}</span><span className="day-label"><strong>Day {item.day}</strong><small>{item.theme || formatDate(item.date)}</small></span><span className="day-count">{item.activities.length}</span>
            </button>)}
          </section>
          <RefinementCard {...props} />
          <section className="summary-metrics">
            <div className="sidebar-section-head"><h2>Trip overview</h2></div>
            <Metric icon="payments" label="Estimated activity costs" value={formatINR(response.summary.estimated_cost)} />
            <Metric icon="restaurant" label="Suggested meal costs" value={formatINR(response.summary.meal_cost)} />
            <Metric icon="account_balance_wallet" label="Known activity + meal estimates" value={formatINR(response.summary.estimated_known_total)} />
            <Metric icon="event_note" label="Planned activities" value={String(response.summary.major_activities)} />
            <Metric icon="schedule" label="Estimated local travel" value={formatDuration(response.summary.estimated_travel_time)} />
            <small className="cost-disclaimer">Known dataset estimates only; excludes lodging, intercity travel, and unpriced items.</small>
          </section>
        </aside>
        <section className="itinerary-main">
          {props.refining && <RefinementLoading />}
          {props.view === "timeline" ? <Timeline
            day={day}
            response={response}
            onAddRecommendation={props.onAddRecommendation}
            addingRecommendation={props.addingRecommendation}
          /> : <Suspense fallback={<div className="map-fallback" role="status">Loading map…</div>}>
            <MapLibreView
              day={day}
              meals={response.meal_suggestions}
              destination={props.request?.destination ?? null}
            />
          </Suspense>}
          <EvidencePanel response={response} />
        </section>
      </div>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: string; label: string; value: string }) {
  return <div className="metric"><span className="material-symbols-outlined">{icon}</span><span>{label}</span><strong>{value}</strong></div>;
}

function AskJourniPanel({
  day,
  onAsk,
  onAddRecommendation,
  addingRecommendation,
}: {
  day: TripResponse["days"][number] | undefined;
  onAsk: (question: string) => Promise<ChatResponse>;
  onAddRecommendation: (day: number, recommendation: NearbyRecommendation) => Promise<void>;
  addingRecommendation: string;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [error, setError] = useState("");
  const [recommendationError, setRecommendationError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitQuestion(value: string) {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    setQuestion(trimmed);
    setError("");
    setLoading(true);
    try {
      setAnswer(await onAsk(trimmed));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "JOURNI could not answer that question.");
    } finally {
      setLoading(false);
    }
  }

  const suggestions = [
    "Why did you choose these places?",
    `What can I do on Day ${day?.day ?? 1}?`,
    "What assumptions are being made?",
  ];
  return <section className="ask-journi-card">
    <button className="ask-journi-toggle" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
      <span><span className="material-symbols-outlined">auto_awesome</span> Ask JOURNI AI</span>
      <span className="material-symbols-outlined">{open ? "expand_less" : "expand_more"}</span>
    </button>
    {open && <div className="ask-journi-content">
      <p>Ask about this itinerary. Answers use your trip details and JOURNI's place data.</p>
      <div className="ask-journi-prompts">{suggestions.map((suggestion) =>
        <button key={suggestion} type="button" disabled={loading} onClick={() => void submitQuestion(suggestion)}>{suggestion}</button>
      )}</div>
      <form onSubmit={(event) => { event.preventDefault(); void submitQuestion(question); }}>
        <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={1000} placeholder="Ask about your current trip…" disabled={loading} aria-label="Ask about your current trip" />
        <button className="ask-journi-send" type="submit" aria-label="Send question" disabled={!question.trim() || loading}><span className="material-symbols-outlined">{loading ? "progress_activity" : "arrow_forward"}</span></button>
      </form>
      {loading && <p className="ask-journi-status" role="status">Checking your itinerary…</p>}
      {error && <p className="ask-journi-error" role="alert">{error}</p>}
      {answer && <div className="ask-journi-answer" aria-live="polite">
        <small>{answer.requires_refinement ? "Use Refine Itinerary for changes" : answer.provider === "gemini" ? "JOURNI AI · Gemini" : "JOURNI data fallback"}</small>
        <p>{answer.answer}</p>
      </div>}
      {answer?.recommendations.length ? <div className="chat-recommendations">
        <strong>Suggested JOURNI dataset places</strong>
        {answer.recommendations.map((recommendation) => <article className="nearby-card" key={recommendation.place_id}>
          <div className="nearby-card-main">
            <strong>{recommendation.name}</strong>
            <small>{recommendation.category || "Place"} · {recommendation.distance_km.toFixed(1)} km · ~{formatDuration(recommendation.travel_minutes)} travel</small>
            <p>{recommendation.reason}</p>
            <div className="nearby-evidence"><span>{recommendation.place_evidence}</span><span>{recommendation.distance_evidence} distance/time</span></div>
          </div>
          <button className="button button-soft nearby-add" type="button" disabled={Boolean(addingRecommendation)} onClick={() => {
            setRecommendationError("");
            void onAddRecommendation(day?.day ?? 1, recommendation)
              .then(() => setAnswer((current) => current
                ? { ...current, recommendations: current.recommendations.filter((item) => item.place_id !== recommendation.place_id) }
                : current))
              .catch((cause: unknown) => {
                setRecommendationError(cause instanceof Error ? cause.message : "JOURNI could not add this place.");
              });
          }}>{addingRecommendation === recommendation.place_id ? "Checking…" : "Add to Day"}</button>
        </article>)}
        {recommendationError && <p className="nearby-error" role="alert">{recommendationError}</p>}
      </div> : null}
      <small className="ask-journi-note">JOURNI AI won't change your itinerary from chat.</small>
    </div>}
  </section>;
}

function JourneyStrip({ request, response, ticketName, ticketUrl, ticketError, onTicketFile, onClearTicket }: {
  request: TripRequest;
  response: TripResponse;
  ticketName: string;
  ticketUrl: string;
  ticketError: string;
  onTicketFile: (file: File | null) => void;
  onClearTicket: () => void;
}) {
  const journey = request.journey;
  const journeyResponse = response.journey;
  const ownTransport = journey?.transport === "car" || journey?.transport === "scooter/bike";
  const status = journey?.status === "confirmed"
    ? ownTransport ? "Confirmed" : "Booked / confirmed"
    : journey?.status === "planned"
      ? "Planned"
      : journey?.status === "not_booked"
        ? "Not booked yet"
        : "Timing not confirmed";
  const icon = journey?.transport === "train"
    ? "train"
    : journey?.transport === "bus"
      ? "directions_bus"
      : journey?.transport === "car" || journey?.transport === "taxi"
        ? "directions_car"
        : "commute";
  return <section className="journey-strip page-wrap" aria-label="Intercity journey">
    <span className="journey-icon material-symbols-outlined">{icon}</span>
    <div className="journey-route">
      <strong>{request.origin.city} <span>→</span> {request.destination.city}</strong>
      <small>{journey?.departure_at && journey.arrival_at ? `${journey.transport} · ${formatJourneyDateTime(journey.departure_at)} → ${formatJourneyDateTime(journey.arrival_at)}` : `${journey?.transport ?? "Intercity"} · Arrival ${request.arrival} · final-day departure ${request.departure} (assumed)`}</small>
    </div>
    <div className="journey-duration"><small>INTERCITY JOURNEY</small><strong>{journeyResponse?.duration_minutes != null ? formatDuration(journeyResponse.duration_minutes) : "No exact duration"}</strong></div>
    <div className="journey-status">
      <span className="journey-status-badge">{status}</span>
      <div className="ticket-state"><span className="material-symbols-outlined">confirmation_number</span>{ticketName ? "Ticket attached" : "No ticket attached"}</div>
    </div>
    <div className="journey-actions">
      {ticketName
        ? <><a className="text-button" href={ticketUrl} target="_blank" rel="noopener noreferrer">View ticket <span aria-hidden="true">→</span></a><button className="text-button ticket-remove" type="button" onClick={onClearTicket}>Remove</button></>
        : <label className="text-button ticket-attach">Attach ticket<input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(event) => void onTicketFile(event.target.files?.[0] ?? null)} /></label>}
    </div>
    <LocalClock />
    {ticketError && <small className="journey-ticket-error" role="alert">{ticketError}</small>}
  </section>;
}

function LocalClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const localTime = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(now);
  return <div className="journey-clock"><small>INDIA LOCAL TIME</small><strong>{localTime}</strong></div>;
}

function RefinementCard({ refinement, onRefinement, refining, refinementError, onRefine, onRetryRefinement }: DashboardProps) {
  return <section className="refinement-card">
    <div className="refinement-title"><span className="material-symbols-outlined">auto_awesome</span><div><h2>Refine your itinerary</h2><small>Describe a change in your own words.</small></div></div>
    <form onSubmit={onRefine}>
      <textarea value={refinement} onChange={(event) => onRefinement(event.target.value)} placeholder="e.g. Make Day 2 more relaxed and focus on culture." rows={3} disabled={refining} />
      <button className="button button-primary refine-submit" type="submit" disabled={!refinement.trim() || refining}>{refining ? "Updating…" : "Update itinerary"}<span className="material-symbols-outlined">{refining ? "progress_activity" : "arrow_forward"}</span></button>
    </form>
    {refinementError && <div className="refine-error" role="alert"><p>We couldn't update the itinerary. Your current itinerary is unchanged.</p><small>{refinementError}</small><button className="text-button" onClick={onRetryRefinement}>Retry refinement</button></div>}
  </section>;
}

function RefinementLoading() {
  return <div className="refinement-progress" role="status"><span className="spinner" /><div><strong>Updating your itinerary</strong><p>Understanding your request · Replanning · Checking constraints</p></div></div>;
}

function Timeline({
  day,
  response,
  onAddRecommendation,
  addingRecommendation,
}: {
  day: TripResponse["days"][number] | undefined;
  response: TripResponse;
  onAddRecommendation: (day: number, recommendation: NearbyRecommendation) => Promise<void>;
  addingRecommendation: string;
}) {
  if (!day) return <EmptyDay />;
  const explanation = response.ai_explanation?.day_explanations[String(day.day)];
  const meals = response.meal_suggestions.filter((meal) => meal.day === day.day && meal.scheduled);
  const entries = [
    ...day.activities.map((activity) => ({
      kind: "activity" as const,
      start_time: activity.start_time,
      end_time: activity.end_time,
      activity,
    })),
    ...meals.flatMap((meal) => meal.start_time && meal.end_time
      ? [{ kind: "meal" as const, start_time: meal.start_time, end_time: meal.end_time, meal }]
      : []),
  ].sort((left, right) => left.start_time.localeCompare(right.start_time));
  const mealCost = meals.reduce((total, meal) => total + (meal.price ?? 0), 0);
  const activityCost = day.activities.reduce((total, activity) => total + activity.estimated_cost, 0);
  return <section className="timeline-panel">
    <div className="timeline-header"><div><span className="section-kicker">{formatDate(day.date)} · DAY {day.day}</span><h2>{day.theme || `Day ${day.day}`}</h2></div><span className="activity-total">{day.activities.length} {day.activities.length === 1 ? "activity" : "activities"} · {meals.length} {meals.length === 1 ? "meal" : "meals"}</span></div>
    <p className="day-cost-summary">Activity estimates {formatINR(activityCost)} · Suggested meals {formatINR(mealCost)}</p>
    {explanation && <p className="day-explanation">{explanation}</p>}
    {entries.length ? <div className="timeline-list">
      {entries.map((entry, index) => <article className={entry.kind === "meal" ? "activity-row meal-time-row" : "activity-row"} key={entry.kind === "meal" ? `${entry.meal.restaurant}-${entry.start_time}` : `${entry.activity.place_id}-${index}`}>
        <div className="activity-time">{entry.start_time}<span>{entry.end_time}</span></div>
        <div className="timeline-rail"><span className={entry.kind === "meal" ? "timeline-dot meal" : "timeline-dot"}>{index + 1}</span>{index < entries.length - 1 && <span className="timeline-line" />}</div>
        <div className="activity-card">
          {entry.kind === "meal" ? <>
            <div className="activity-heading"><span className="category-tag">Meal suggestion</span><span className="activity-duration"><span className="material-symbols-outlined">schedule</span>60 min dining window</span></div>
            <h3>{entry.meal.restaurant}</h3>
            <p>{entry.meal.meal}{entry.meal.cuisine ? ` · ${entry.meal.cuisine}` : ""}. Restaurant availability is not checked.</p>
            <div className="activity-meta">
              {entry.meal.price != null && <span><span className="material-symbols-outlined">payments</span>Dataset estimate {formatINR(entry.meal.price)}</span>}
              {entry.meal.source && <span><span className="material-symbols-outlined">database</span>{entry.meal.source}</span>}
            </div>
            {(entry.meal.lat == null || entry.meal.lng == null) && <div className="unknown-inline">Restaurant location and travel time are unknown; this timed suggestion is not routed between activity stops.</div>}
          </> : <>
            <div className="activity-heading"><span className="category-tag">{entry.activity.category || "Planned stop"}</span><span className="activity-duration"><span className="material-symbols-outlined">schedule</span>{formatDuration(entry.activity.duration_minutes)} at this place</span></div>
            <h3>{entry.activity.name}</h3>
            <p>{entry.activity.reason}</p>
            <div className="activity-meta">
              <span><span className="material-symbols-outlined">payments</span>Est. {formatINR(entry.activity.estimated_cost)}</span>
              {entry.activity.travel_minutes > 0 && <span><span className="material-symbols-outlined">directions_walk</span>{formatDuration(entry.activity.travel_minutes)} local travel from previous stop <em>DERIVED</em></span>}
              {entry.activity.source && <span><span className="material-symbols-outlined">database</span>{entry.activity.source}</span>}
            </div>
            {(entry.activity.lat == null || entry.activity.lng == null) && <div className="unknown-inline">Map coordinates unavailable for this stop.</div>}
          </>}
        </div>
      </article>)}
    </div> : <EmptyDay />}
    {day.limited_activities && <NearbyOptions
      day={day}
      onAdd={onAddRecommendation}
      addingRecommendation={addingRecommendation}
    />}
  </section>;
}

function NearbyOptions({
  day,
  onAdd,
  addingRecommendation,
}: {
  day: TripResponse["days"][number];
  onAdd: (day: number, recommendation: NearbyRecommendation) => Promise<void>;
  addingRecommendation: string;
}) {
  const [error, setError] = useState("");
  if (!day.limited_activities && !day.recommendations.length) return null;
  return <section className="nearby-options">
    {day.limited_activities && <div className="nearby-limited">
      <span className="material-symbols-outlined">info</span>
      <div><strong>Limited activities found</strong><p>We couldn't find enough suitable places matching your interests and travel constraints. No activities have been fabricated or duplicated.</p></div>
    </div>}
    <div className="nearby-heading"><div><span className="section-kicker">JOURNI DATASET</span><h3>{day.limited_activities ? "More nearby options" : "Other suitable options"}</h3></div></div>
    {day.recommendations.length ? <div className="nearby-list">{day.recommendations.map((recommendation) => <article className="nearby-card" key={recommendation.place_id}>
      <div className="nearby-card-main">
        <strong>{recommendation.name}</strong>
        <small>{recommendation.category || "Place"} · {recommendation.distance_km.toFixed(1)} km away · ~{formatDuration(recommendation.travel_minutes)} travel</small>
        <p>{recommendation.reason}</p>
        <div className="nearby-evidence"><span>{recommendation.place_evidence}</span><span>{recommendation.distance_evidence} distance/time</span>{recommendation.source && <span>{recommendation.source}</span>}</div>
      </div>
      <button className="button button-soft nearby-add" type="button" disabled={Boolean(addingRecommendation)} onClick={() => {
        setError("");
        void onAdd(day.day, recommendation).catch((cause: unknown) => {
          setError(cause instanceof Error ? cause.message : "JOURNI could not add this place.");
        });
      }}>{addingRecommendation === recommendation.place_id ? "Checking…" : "Add to Day"}</button>
    </article>)}</div> : day.limited_activities ? <p className="nearby-empty">No suitable nearby options fit the remaining time and transport constraints.</p> : null}
    {error && <p className="nearby-error" role="alert">{error}</p>}
  </section>;
}

function EmptyDay() {
  return <div className="empty-day"><span className="material-symbols-outlined">event_busy</span><h3>No activities scheduled</h3><p>The planner did not add stops to this day.</p></div>;
}

function EvidencePanel({ response }: { response: TripResponse }) {
  return <section className="evidence-panel">
    <div className="evidence-title"><span className="material-symbols-outlined">verified_user</span><div><span className="section-kicker">DATA TRANSPARENCY</span><h2>Evidence & assumptions</h2></div></div>
    {response.evidence.length > 0 ? <div className="evidence-grid">{response.evidence.map((item, index) => <article className="evidence-card" key={`${item.label}-${index}`}><div className="evidence-card-head"><strong>{item.label}</strong><span className={`evidence-badge ${item.value.toLowerCase()}`}>{item.value}</span></div>{item.notes && <p>{item.notes}</p>}{item.source && <small>Source: {item.source}</small>}</article>)}</div> : <p className="muted-copy">The planner did not return evidence details for this itinerary.</p>}
    {response.assumptions.length > 0 && <div className="assumptions-block"><h3>Planner assumptions</h3><ul>{response.assumptions.map((assumption, index) => <li key={`${index}-${assumption}`}>{assumption}</li>)}</ul></div>}
    {response.validation.checks && <details className="validation-details"><summary>Validation checks</summary><div>{Object.entries(response.validation.checks).map(([name, passed]) => <span key={name} className={passed ? "check-item ok" : "check-item unknown"}><span className="material-symbols-outlined">{passed ? "check_circle" : "help"}</span>{name.replaceAll("_", " ")}: {passed ? "passed" : "not verified / not passed"}</span>)}</div></details>}
  </section>;
}

function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function formatDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function formatJourneyDateTime(value: string): string {
  const [date, time] = value.split("T");
  return `${formatDate(date)} ${time?.slice(0, 5) ?? ""}`;
}

function Footer() {
  return <footer className="site-footer"><div><strong>JOURNI</strong><span>Thoughtful itineraries, transparently planned.</span></div><small>Planning estimates are not live travel, venue, or availability data.</small></footer>;
}

export default App;
