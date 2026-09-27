# JOURNI

## Journey Optimized for Unique Real-world Needs & Interests

JOURNI is a personalized AI-assisted trip-planning prototype designed to transform traveller preferences, constraints, and trip details into a practical day-by-day itinerary.

The system combines a **deterministic planning engine** with **Gemini-powered natural-language intelligence**.

> **The deterministic planner decides the itinerary. Gemini helps understand, explain, and refine it.**

Gemini is intentionally not responsible for inventing destinations, selecting arbitrary places, calculating authoritative travel information, or generating the final itinerary. The backend planning engine remains the source of truth.

---

# 1. Project Overview

Traditional itinerary generators often produce attractive-looking recommendations without enforcing the practical constraints required to make an itinerary usable.

JOURNI approaches trip planning as a constrained planning problem.

A traveller provides:

- Origin
- Destination
- Travel dates
- Number of nights
- Traveller type
- Party composition
- Interests
- Travel pace
- Budget level
- Preferred transport
- Walking tolerance
- Dietary requirements
- Places or categories to avoid
- Other supported planning constraints

JOURNI then processes those preferences through a deterministic planning pipeline:

1. Resolves the requested destination.
2. Retrieves relevant candidate places.
3. Applies hard constraints.
4. Scores and ranks candidates.
5. Groups places geographically.
6. Builds a day-by-day schedule.
7. Estimates travel time between activities.
8. Adds supported meal suggestions.
9. Validates the itinerary.
10. Repairs or replans when validation detects recoverable problems.
11. Produces evidence describing what is known, derived, or unavailable.
12. Optionally uses Gemini to explain the resulting itinerary.
13. Allows natural-language refinement of the generated plan.

The resulting itinerary is presented through a React-based planning interface containing:

- Trip summary
- Journey information
- Daily itinerary
- Activity timeline
- Travel times
- Meal suggestions
- Cost information
- Evidence semantics
- Planner validation
- Map visualization
- Recommendations
- AI explanation
- Natural-language refinement
- Ask JOURNI AI

---

# 2. Why JOURNI Uses a Deterministic Planner

JOURNI deliberately separates **planning decisions** from **language generation**.

An LLM is useful for understanding natural language and explaining decisions, but it is not treated as the authoritative source for structured travel data.

Gemini should not independently invent:

- A place
- A coordinate
- A restaurant location
- A price
- Opening hours
- Travel distance
- Hotel availability
- Booking confirmation
- A final itinerary

Instead, those decisions come from the deterministic JOURNI backend and its available data.

This gives the system a clear separation of responsibility:

```text
Traveller Input
      │
      ▼
Deterministic JOURNI Planner
      │
      ├── Candidate Retrieval
      ├── Hard Constraints
      ├── Scoring
      ├── Geographic Planning
      ├── Scheduling
      ├── Validation
      └── Repair / Replanning
      │
      ▼
Validated Itinerary
      │
      ├───────────────┐
      ▼               ▼
 React Frontend     Gemini
                    │
                    ├── Natural-language interpretation
                    ├── Explanation
                    ├── Refinement understanding
                    └── Trip Q&A
```

---

# 3. High-Level Architecture

```text
Browser
   │
   │ POST /api/trips/plan
   ▼
React Frontend
   │
   │ TripRequest JSON
   ▼
FastAPI
   │
   ▼
PlanningEngine
   │
   ├── CandidateRetrieval
   ├── HardConstraintEngine
   ├── ScoringEngine
   ├── GeographicPlanner
   ├── DailyScheduler
   ├── Validator
   └── Repair / Replan
   │
   ▼
Validated Itinerary
   │
   ├── MealSuggestionService
   ├── Evidence Information
   └── Gemini Explanation
   │
   ▼
TripResponse
   │
   ▼
React Itinerary Dashboard
```

The frontend communicates with the backend through the API rather than duplicating the planning algorithm.

The backend remains responsible for the actual itinerary construction.

---

# 4. Core Planning Pipeline

## 4.1 Candidate Retrieval

The first stage retrieves candidate places relevant to the requested destination.

The retrieval layer works with the canonical place and city data available to the backend.

The candidate retrieval process includes destination/city resolution and supports city aliases where required.

The planner does not ask Gemini to invent candidate places.

```text
Destination
    │
    ▼
City / Alias Resolution
    │
    ▼
Candidate Places
    │
    ▼
Planning Pipeline
```

If no suitable candidates are available, the planner can return an underfilled itinerary rather than inventing activities.

## 4.2 Hard Constraints

Candidate places are filtered using deterministic rules.

Examples include:

- Destination compatibility
- Avoid constraints
- Traveller compatibility where supported
- Budget constraints
- Distance constraints
- Other supported planner constraints

```text
Hard constraint
    ↓
Candidate is removed

Soft preference
    ↓
Candidate remains but receives a different score
```

---

# 5. Personalization and Scoring

After hard filtering, JOURNI scores the remaining candidates.

The scoring system considers information such as:

- Traveller interests
- Budget
- Place confidence
- Candidate suitability
- Other supported profile information

The current prototype represents selected interests with equal weights:

```text
{
    "culture": 1.0,
    "food": 1.0,
    "nature": 1.0
}
```

The interface captures which interests matter, but does not currently provide a user-facing priority gradient.

The planner can still differentiate places by the number of matching interests.

---

# 6. Geographic Planning

After candidates are scored, JOURNI groups them geographically.

The geographic planner uses available place coordinates to reduce unnecessary movement between activities.

The current approach uses deterministic geographic calculations and a greedy nearest-neighbour style grouping strategy.

```text
Candidate Places
       │
       ▼
Coordinates
       │
       ▼
Geographic Grouping
       │
       ▼
Daily Activity Groups
```

The map is intended for geographic orientation and does not claim to provide live road routing or turn-by-turn navigation.

---

# 7. Travel-Time Estimation

JOURNI calculates estimated travel time between activities using available geographic coordinates and transport assumptions.

The system uses:

- Geographic distance
- Transport mode
- Configured transport speeds

Travel time is therefore a **DERIVED** value rather than a live navigation result.

The system does not provide:

- Live traffic
- Turn-by-turn navigation
- Live road conditions
- Real-time route optimization

---

# 8. Scheduling

The scheduler converts geographically grouped places into a practical daily timeline.

It considers:

- Day start time
- Activity duration
- Travel time
- Arrival timing
- Departure timing
- Inter-activity buffers
- Available daily planning window
- Opening-hour information where available

Activities are assigned:

```text
start_time
end_time
travel_minutes
duration
```

The scheduler avoids adding an activity when it cannot fit into the available planning window.

---

# 9. Arrival and Departure Timing

JOURNI separates the intercity journey from the local itinerary.

```text
Origin
   │
   │ Intercity journey
   ▼
Destination
   │
   │ Arrival buffer
   ▼
First local activity
```

Arrival and departure buffers are considered when constructing daily schedules.

---

# 10. Validation

After scheduling, JOURNI validates the resulting itinerary.

Validation checks include:

- Date validity
- Duplicate activities
- Schedule consistency
- Geographic consistency
- Budget-related constraints
- Other planner invariants

```text
Generated Itinerary
        │
        ▼
    Validator
        │
   ┌────┴────┐
   │         │
 PASS      FAIL
   │         │
   ▼         ▼
Return    Repair /
result    Replan
```

The frontend exposes the validation result to the traveller.

---

# 11. Repair and Replanning

JOURNI includes a bounded repair loop.

When the generated itinerary violates recoverable planning constraints, the system can attempt to repair or replan it.

```text
Plan
 │
 ▼
Validate
 │
 ├── Passed → Return itinerary
 │
 └── Failed
       │
       ▼
     Repair
       │
       ▼
     Replan
       │
       ▼
     Validate
       │
       └── bounded attempts
```

The repair process is bounded rather than running indefinitely.

---

# 12. Meals and Restaurant Suggestions

JOURNI can enrich itineraries with meal suggestions.

Supported meal windows include:

- Lunch
- Dinner

Meal suggestions are inserted only when they can fit into the daily schedule without creating an obvious timing conflict.

Restaurant coordinates are not currently available in the dataset used by the prototype.

Therefore JOURNI does not:

- Invent restaurant coordinates
- Draw fake restaurant markers
- Claim exact restaurant travel time
- Pretend restaurants are geographically routed

When restaurant location information is unavailable, the UI explicitly communicates that limitation:

```text
Restaurant location and travel time are unknown;
this timed suggestion is not routed between activity stops.
```

---

# 13. Evidence Semantics

JOURNI distinguishes between information directly supported by data, information calculated by the planner, and information that is unavailable.

The three evidence categories are:

```text
FACT
DERIVED
UNKNOWN
```

## FACT

Information directly supported by the underlying data.

Examples:

- Place name stored in the database
- Destination coordinate stored in the database
- Dataset-provided cost
- Dataset-provided category

## DERIVED

Information calculated by JOURNI from available data.

Examples:

- Haversine geographic distance
- Estimated travel time
- Geographic grouping
- Activity ordering
- Planner score
- Scheduling decisions

## UNKNOWN

Information that JOURNI does not have enough data to establish.

Examples:

- Missing opening hours
- Missing accessibility information
- Restaurant coordinates
- Live traffic
- Hotel availability
- Booking status

The system intentionally prefers `UNKNOWN` over inventing a plausible-looking value.

---

# 14. Gemini Integration

Gemini is integrated as a bounded intelligence layer.

The system uses Gemini for:

- Natural-language interpretation
- Itinerary explanation
- Natural-language refinement understanding
- Trip questions and answers

Gemini is not the authoritative itinerary generator.

---

# 15. Gemini — Itinerary Explanation

After the deterministic planner generates and validates an itinerary, Gemini can be given structured planning context and asked to explain the resulting plan.

```text
Planner
   │
   │ validated itinerary
   ▼
Gemini
   │
   ▼
Natural-language explanation
```

The explanation can describe:

- Why selected activities fit the traveller's interests
- Why the itinerary has a particular pace
- How activities are organized
- Relevant cost context
- Important assumptions or limitations

Gemini should not fabricate unsupported facts.

---

# 16. Gemini — Natural-Language Refinement

Example:

```text
Make Day 2 more relaxed and add more culture.
```

The refinement process is:

```text
Natural-language request
        │
        ▼
      Gemini
        │
        ▼
Structured refinement command
        │
        ▼
Deterministic planner
        │
        ▼
Replanned itinerary
        │
        ▼
Validation
        │
        ▼
Updated itinerary
```

Gemini interprets the natural-language request.

The deterministic planner executes the actual planning change.

---

# 17. Ask JOURNI AI

The frontend provides an Ask JOURNI AI interface.

Example:

```text
Why did you choose these places for Day 2?
```

The request is sent to:

```http
POST /api/trips/chat
```

The backend provides the relevant trip context to the language layer.

If Gemini is unavailable, the backend can use a structured deterministic fallback where supported.

---

# 18. API Endpoints

## Plan a trip

```http
POST /api/trips/plan
```

Input: `TripRequest`

Output: `TripResponse`

## Refine a trip

```http
POST /api/trips/refine
```

Input: `RefineRequest`

Output: `TripResponse`

## Ask JOURNI AI

```http
POST /api/trips/chat
```

Input: `ChatRequest`

Output: `ChatResponse`

## Add a recommendation

```http
POST /api/trips/recommendations/add
```

The backend rechecks planning eligibility before adding a recommendation.

## Health

```http
GET /api/health
```

Returns backend health and relevant service configuration information without exposing credentials.

---

# 19. Recommendations

JOURNI can provide additional recommendations based on deterministic JOURNI data and planner context.

The recommendation process considers factors such as:

- Destination
- Traveller preferences
- Interests
- Budget
- Distance
- Transport mode
- Remaining time
- Existing visited activities
- Available place data

When the user chooses to add a recommendation, the backend rechecks the candidate and schedules it through the planning system.

---

# 20. Map

The current implementation uses:

- MapLibre
- OpenStreetMap-based map tiles
- Returned place coordinates
- Activity markers
- Stop numbering
- Visual connections between itinerary stops

The displayed connection between stops is **not a live road route**.

The map does not provide:

- Turn-by-turn navigation
- Live traffic
- Live route optimization
- Real-time road conditions

---

# 21. Frontend

The frontend is implemented using:

- React
- TypeScript
- Vite

The interface follows the Stitch-designed JOURNI product direction.

The original Stitch source is retained separately and is not used as the production runtime frontend.

---

# 22. Frontend User Flow

The interface follows a seven-step trip planning flow:

1. Origin and destination
2. Dates and trip duration
3. Traveller and party information
4. Interests and pace
5. Budget and daily start
6. Special requirements
7. Trip generation

Special requirements can include:

- Dietary requirements
- Constraints
- Avoid preferences
- Other supported traveller requirements

---

# 23. Itinerary Dashboard

After planning, the dashboard presents:

- Trip overview
- Destination
- Journey information
- Day-by-day itinerary
- Activity timeline
- Travel times
- Costs
- Meal suggestions
- Evidence information
- Planner validation
- Recommendations
- Map
- AI explanation
- Refinement controls

---

# 24. Journey Information

JOURNI separates the intercity journey from local itinerary activities.

The journey section can communicate:

- Transport mode
- Journey start
- Journey end
- Journey timing
- Important journey details
- Ticket/document information where supplied by the user

The application does not provide a booking engine.

---

# 25. Cost Information

The itinerary can display available activity costs and meal costs.

The system distinguishes between:

- Known dataset-supported costs
- Estimated/derived values
- Unknown costs

The application does not claim that an unavailable price is exact.

---

# 26. Data Sources

The audited database contains:

```text
places         1,037 rows
cities         3,349 rows
destinations     100 rows
restaurants   139,312 rows
```

The `places` table is the primary source for itinerary activity planning.

The `cities` table supports city and alias resolution.

The restaurant table is used for meal enrichment where supported.

The `destinations` dataset contains richer destination-level information, but the current planner does not query it as part of the authoritative itinerary pipeline.

---

# 27. Place Data

The current place dataset provides structured information used by the planner, including where available:

- Place name
- Destination/city
- Category
- Coordinates
- Interests
- Cost information
- Confidence information
- Other supported place metadata

All audited places currently have latitude and longitude values.

---

# 28. Restaurant Data Limitation

The current restaurant dataset contains approximately:

```text
139,312 restaurants
```

The audited dataset has:

```text
latitude  = NULL
longitude = NULL
```

for restaurant records.

Therefore JOURNI does not invent restaurant coordinates or claim exact restaurant travel time.

The missing information is communicated as UNKNOWN.

---

# 29. Known Limitations

JOURNI is intentionally a prototype rather than a full commercial travel marketplace.

It does not provide:

### Booking

- Flight booking
- Hotel booking
- Restaurant table booking
- Ticket purchasing
- Payment processing

### Live Information

- Live traffic
- Live hotel availability
- Live restaurant availability
- Live weather
- Real-time road conditions
- Turn-by-turn navigation

### Other limitations

- Restaurant coordinates are unavailable.
- Opening hours are only enforced where usable data exists.
- Accessibility information is incomplete where the source data does not establish it.
- Selected interests currently use equal weights.
- Travel times are estimates, not live navigation results.

---

# 30. Error Handling and Fallback Behaviour

Optional AI failures do not necessarily prevent deterministic trip planning.

```text
Gemini available
    ↓
Planner creates itinerary
    ↓
Gemini adds explanation
    ↓
Full response
```

or:

```text
Gemini unavailable
    ↓
Planner creates itinerary
    ↓
Deterministic fallback
    ↓
Trip remains usable
```

Gemini is an enhancement layer rather than the core planning engine.

---

# 31. Project Structure

```text
journi/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── db/
│   │   ├── llm/
│   │   ├── models/
│   │   ├── planner/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── validation/
│   ├── data/
│   ├── scripts/
│   ├── tests/
│   ├── .env.example
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   │   └── locations.json
│   ├── scripts/
│   ├── .env.example
│   └── package.json
│
├── stitch_apex_saas_web_application/
│   └── Original Stitch design source
│
├── .gitignore
├── README.md
└── ...
```

---

# 32. Local Development

## Backend

```powershell
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

Default backend:

```text
http://localhost:8000
```

The Gemini API key must remain local and must never be committed.

## Frontend

Open a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend uses:

```text
VITE_API_BASE_URL
```

to locate the backend API.

---

# 33. Location Catalog

The frontend contains:

```text
frontend/public/locations.json
```

Refresh it when canonical backend location datasets change:

```powershell
.rontend\scriptsuild-location-catalog.ps1
```

---

# 34. Environment Variables

Backend configuration belongs in:

```text
backend/.env
```

A safe template is provided in:

```text
backend/.env.example
```

Example:

```text
GEMINI_API_KEY=<local-secret>
GEMINI_MODEL_NAME=<configured-model>
```

The actual API key must never be committed.

---

# 35. Security Principles

- API keys stay server-side.
- Actual `.env` files stay local and ignored.
- The frontend does not receive the Gemini API key.
- The health endpoint does not expose credentials.
- The repository should contain safe configuration templates rather than private credentials.

---

# 36. Testing

Run backend tests:

```powershell
cd backend
pytest
```

The audited project had:

```text
91 passed
```

The suite covers areas including:

- City resolution
- Journey timing
- LLM fallback
- Null behaviour
- Planner behaviour
- Recommendations
- Chat
- Refinement
- Reliability
- Restaurant enrichment
- Database integration

Run frontend linting:

```powershell
cd frontend
npm run lint
```

Run the production build:

```powershell
npm run build
```

---

# 37. Example Trip 1 — Balanced Cultural Trip

```text
Traveller:
Solo

Origin:
Bengaluru

Destination:
Goa

Duration:
3 nights

Interests:
Culture
Food

Pace:
Balanced

Budget:
Moderate
```

Expected planning flow:

```text
Traveller preferences
        ↓
Retrieve destination candidates
        ↓
Apply hard constraints
        ↓
Score culture / food relevance
        ↓
Group geographically
        ↓
Schedule across available days
        ↓
Validate
        ↓
Return itinerary
```

The exact activity count depends on available data and constraints.

The planner should not invent activities when insufficient candidates are available.

---

# 38. Example Trip 2 — Family Cultural Trip

```text
Traveller:
Family

Origin:
Mumbai

Destination:
Agra

Duration:
2 nights

Interests:
Culture
Sightseeing

Pace:
Easy-going

Budget:
Moderate
```

Expected behaviour:

- Retrieve relevant candidates.
- Apply traveller and budget constraints.
- Prefer culturally relevant places.
- Use geographic grouping.
- Keep the schedule within the configured planning window.
- Validate the itinerary.
- Preserve evidence semantics.
- Provide an explanation when Gemini is available.

---

# 39. Example Trip 3 — Couple Food and Culture Trip

```text
Traveller:
Couple

Origin:
Hyderabad

Destination:
Jaipur

Duration:
4 nights

Interests:
Culture
Food

Pace:
Packed

Budget:
Premium
```

Expected behaviour:

- Retrieve Jaipur candidates.
- Apply hard constraints.
- Score culture and food matches.
- Group activities geographically.
- Build a more activity-dense schedule consistent with the selected pace.
- Add supported meal suggestions.
- Estimate travel time between stops.
- Validate the itinerary.
- Provide Gemini explanation/refinement when configured.

---

# 40. Example Natural-Language Refinement

```text
Make Day 2 more relaxed and add more culture.
```

Architecture:

```text
Natural-language request
          │
          ▼
        Gemini
          │
          ▼
Structured refinement command
          │
          ▼
Deterministic planner
          │
          ▼
Replanned Day 2
          │
          ▼
Validation
```

---

# 41. Example AI Explanation

The traveller can ask:

```text
Why did you choose these places for Day 2?
```

The explanation layer can use planner context such as:

- Traveller interests
- Pace
- Budget
- Selected activities
- Activity categories
- Activity timing
- Planning reasons
- Available assumptions

The purpose is to make the deterministic planner's output understandable, not to create unsupported travel facts.

---

# 42. Example Evidence

```text
Place:
Example Fort

Evidence:
FACT
```

A calculated travel estimate:

```text
Travel:
28 minutes

Evidence:
DERIVED
```

Unavailable restaurant coordinates:

```text
Restaurant coordinates:
UNKNOWN
```

This distinction is preserved throughout the backend and frontend.

---

# 43. Design Philosophy

JOURNI is built around four principles.

## 1. Deterministic planning

Planning decisions should be reproducible and inspectable.

## 2. Bounded AI

Gemini should enhance the system without becoming its source of truth.

## 3. Evidence-aware output

Known facts, calculated values, and unavailable information should be clearly distinguished.

## 4. Graceful degradation

The application should remain useful when optional AI functionality is unavailable.

---

# 44. What JOURNI Does Not Claim

JOURNI does not claim to be:

- A full travel booking platform
- A hotel marketplace
- A flight booking service
- A restaurant reservation service
- A live navigation application
- A real-time traffic engine
- A weather forecasting service
- A live availability platform
- A replacement for professional navigation or booking services

It is a personalized trip-planning prototype focused on demonstrating:

- Data-driven planning
- Constraint handling
- Personalization
- Geographic organization
- Scheduling
- Validation
- Repair/replanning
- Evidence semantics
- Bounded LLM integration
- Natural-language refinement
- A polished planning interface

---

# 45. Technology Stack

## Backend

- Python
- FastAPI
- Pydantic
- SQLite
- SQLAlchemy / database layer
- Deterministic planning modules
- Google Gemini API

## Frontend

- React
- TypeScript
- Vite
- MapLibre

## Mapping

- MapLibre
- OpenStreetMap-based map data

## AI

- Google Gemini
- Server-side integration
- Structured refinement/explanation flow
- Deterministic fallback behaviour

---

# 46. Architectural Responsibility Matrix

| Responsibility | Deterministic Planner | Gemini | Frontend |
|---|---:|---:|---:|
| Retrieve places | ✓ | | |
| Apply hard constraints | ✓ | | |
| Score candidates | ✓ | | |
| Geographic grouping | ✓ | | |
| Schedule activities | ✓ | | |
| Estimate travel time | ✓ | | |
| Validate itinerary | ✓ | | |
| Repair/replan | ✓ | | |
| Interpret natural-language refinement | | ✓ | |
| Explain itinerary | | ✓ | |
| Answer trip questions | | ✓ | |
| Render itinerary | | | ✓ |
| Render map | | | ✓ |
| Collect traveller input | | | ✓ |
| Display evidence | | | ✓ |
| Display validation | | | ✓ |

Central rule:

```text
Gemini assists.
The planner decides.
The frontend presents.
```

---

# 47. Current Prototype Scope

Included:

```text
✓ Personalized trip input
✓ Destination resolution
✓ Candidate retrieval
✓ Hard constraints
✓ Scoring
✓ Geographic planning
✓ Scheduling
✓ Travel-time estimation
✓ Validation
✓ Repair/replanning
✓ Meal enrichment
✓ Recommendations
✓ Evidence semantics
✓ Map
✓ Gemini explanation
✓ Natural-language refinement
✓ Ask JOURNI AI
✓ Frontend itinerary dashboard
```

Not included:

```text
✗ Hotel booking
✗ Flight booking
✗ Restaurant reservations
✗ Payments
✗ Live traffic
✗ Live hotel availability
✗ Live restaurant availability
✗ Live weather
✗ Turn-by-turn navigation
✗ User accounts
✗ Social platform
✗ Marketplace
```

This scope is intentional.

---

# 48. Project Development Principle

JOURNI is designed as a practical engineering prototype rather than a collection of disconnected AI features.

The planning flow is:

```text
Understand the traveller
        ↓
Find valid candidates
        ↓
Apply constraints
        ↓
Personalize
        ↓
Organize geographically
        ↓
Schedule
        ↓
Validate
        ↓
Repair if required
        ↓
Explain
        ↓
Refine
```

Each stage has a clear responsibility, making the final itinerary inspectable.

---

# 49. Submission Notes

Before committing the project to version control:

- Keep real API keys out of the repository.
- Keep local `.env` files ignored.
- Keep local databases and development artifacts ignored where appropriate.
- Remove temporary audit/scratch files.
- Verify the backend test suite.
- Verify the frontend lint/build.
- Verify Gemini configuration using a real local request.
- Verify Gemini fallback when Gemini is unavailable.
- Verify that the README reflects the actual implementation.

The repository should contain code and safe configuration templates, not private credentials.

---

# 50. Final Summary

JOURNI demonstrates a hybrid approach to AI-assisted trip planning.

The system does not rely on an LLM to invent an itinerary.

```text
                    JOURNI
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
Deterministic Planner              Gemini
        │                             │
        ├── Retrieval                 ├── Interpretation
        ├── Constraints               ├── Explanation
        ├── Scoring                   ├── Refinement
        ├── Geography                 └── Q&A
        ├── Scheduling
        ├── Validation
        └── Repair
        │
        ▼
Validated Itinerary
        │
        ▼
     React UI
```

The deterministic planner is authoritative.

Gemini provides language intelligence around the planner.

The frontend makes the resulting trip understandable and interactive.

The evidence model distinguishes:

```text
FACT
DERIVED
UNKNOWN
```

so that the system does not need to fabricate information when the underlying data is incomplete.

The result is a prototype focused on transforming traveller preferences and constraints into a practical, explainable, and validated day-by-day itinerary.

---

## License / Project Status

This project is a technical prototype created for the **WishTrip AI Engineering Internship take-home assignment**.

It is not intended to represent a production travel-booking platform.
