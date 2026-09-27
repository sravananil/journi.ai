# JOURNI frontend

React, TypeScript, and Vite frontend based on the Stitch design source in `../stitch_apex_saas_web_application/`.

## Run locally

1. Start the existing FastAPI backend from `../backend/` using its documented environment and database setup.
2. Copy `.env.example` to `.env` if the backend is not at `http://localhost:8000`.
3. Run `npm install`, then `npm run dev`.

The frontend calls `POST /api/trips/plan`, `POST /api/trips/refine`, `POST /api/trips/chat`, and `POST /api/trips/recommendations/add`; request and response types mirror the backend Pydantic schemas. Ask JOURNI AI is trip-scoped and informational. Nearby recommendations come from the backend dataset, and adding one invokes deterministic scheduling and validation. Meal suggestions are placed only in non-overlapping lunch/dinner windows; the restaurant dataset currently has no restaurant coordinates, so restaurant travel and map positions remain unknown.

The itinerary map uses MapLibre GL JS with OpenStreetMap raster tiles. OpenStreetMap attribution is displayed on the map. Attraction markers and the dashed stop sequence use only coordinates returned by JOURNI; the line is not a road route or turn-by-turn directions.

Gemini credentials belong only in `backend/.env` as `GEMINI_API_KEY`. Never add a `VITE_GEMINI_API_KEY` or otherwise send the key to the browser. Set `GEMINI_MODEL_NAME` in `backend/.env` to select the Gemini model; the default is `gemini-2.5-flash`. The `/api/health` response reports the selected model and whether the backend has a Gemini client configured without exposing credentials. If Gemini is unavailable, the planner and refinement continue with their existing deterministic fallback behavior; trip chat answers from the current itinerary where possible.

## Location catalog

`public/locations.json` is generated from the existing `backend/data/processed/cities.csv` and `places.csv`. It contains canonical city coordinates for origins and only destinations present in the planner place data with a city-coordinate match. All catalog entries are in India, matching the source dataset. This avoids client-side geocoding or guessed coordinates.

When those backend data files change, regenerate the snapshot from the workspace root:

```powershell
.\frontend\scripts\build-location-catalog.ps1
```

The backend currently has no location-catalog endpoint, so the bundled list is a snapshot that needs refreshing after data updates.

## Journey timing and documents

Broad arrival/departure periods remain available as conservative scheduling fallbacks. Optional exact outbound times are sent as planning constraints; the backend applies configurable arrival and final-day departure buffers. Intercity duration is shown separately from local stop-to-stop travel estimates.

Optional PDF, PNG, JPG, and JPEG journey documents are stored in this browser's IndexedDB only. They are not uploaded to the backend and are not represented as official tickets.

The backend's nearby recommendation distances are configurable with the `JOURNI_RECOMMENDATION_*_RADIUS_KM` variables in `backend/.env`; evening car and scooter/bike recommendations use the tighter configured radius. All distance and time values are heuristic estimates rather than live routing.
