import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import type { Location, TripResponse } from "../types";
import "maplibre-gl/dist/maplibre-gl.css";
import "./map-view.css";

type MapPoint = {
  name: string;
  time: string;
  lat: number;
  lng: number;
  meal: boolean;
};

type UnresolvedMapPoint = Omit<MapPoint, "lat" | "lng"> & {
  lat?: number | null;
  lng?: number | null;
};

type MapViewProps = {
  day: TripResponse["days"][number] | undefined;
  meals: TripResponse["meal_suggestions"];
  destination: Location | null;
};

const openStreetMapStyle: StyleSpecification = {
  version: 8,
  sources: {
    openstreetmap: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "openstreetmap",
      type: "raster",
      source: "openstreetmap",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

function isMappableCoordinate(lat: number | null | undefined, lng: number | null | undefined): lat is number {
  return (
    typeof lat === "number" &&
    Number.isFinite(lat) &&
    lat >= -90 &&
    lat <= 90 &&
    typeof lng === "number" &&
    Number.isFinite(lng) &&
    lng >= -180 &&
    lng <= 180
  );
}

export function MapView({ day, meals, destination }: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const [mapError, setMapError] = useState("");
  const points = useMemo<MapPoint[]>(() => {
    const candidates: UnresolvedMapPoint[] = [
      ...(day?.activities.map((activity) => ({
        name: activity.name,
        time: activity.start_time,
        lat: activity.lat,
        lng: activity.lng,
        meal: false,
      })) ?? []),
      ...meals
        .filter((meal) => meal.day === day?.day && meal.scheduled)
        .map((meal) => ({
          name: meal.restaurant,
          time: meal.start_time ?? "",
          lat: meal.lat,
          lng: meal.lng,
          meal: true,
        })),
    ];
    return candidates
      .filter((point): point is MapPoint => isMappableCoordinate(point.lat, point.lng))
      .sort((left, right) => left.time.localeCompare(right.time));
  }, [day, meals]);

  useEffect(() => {
    if (!container.current || !destination) return;

    setMapError("");
    const map: MapLibreMap = new maplibregl.Map({
      container: container.current,
      style: openStreetMapStyle,
      center: [destination.lng, destination.lat],
      zoom: 10,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.on("error", () => setMapError("Map tiles could not be loaded. Check your connection and try again."));

    map.on("load", () => {
      if (points.length > 1) {
        map.addSource("itinerary-route", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [{
              type: "Feature",
              properties: {},
              geometry: {
                type: "LineString",
                coordinates: points.map((point) => [point.lng, point.lat]),
              },
            }],
          },
        });
        map.addLayer({
          id: "itinerary-route-line",
          type: "line",
          source: "itinerary-route",
          paint: {
            "line-color": "#b02f00",
            "line-width": 3,
            "line-opacity": 0.8,
            "line-dasharray": [2, 1.5],
          },
        });
      }

      const bounds = new maplibregl.LngLatBounds();
      points.forEach((point, index) => {
        bounds.extend([point.lng, point.lat]);
        const markerElement = document.createElement("button");
        markerElement.type = "button";
        markerElement.className = point.meal ? "journi-map-marker meal" : "journi-map-marker";
        markerElement.textContent = String(index + 1);
        markerElement.setAttribute("aria-label", `${index + 1}. ${point.name} at ${point.time}`);
        const popup = new maplibregl.Popup({ offset: 22 }).setText(
          `${index + 1}. ${point.name}${point.time ? ` · ${point.time}` : ""}`,
        );
        new maplibregl.Marker({ element: markerElement, anchor: "bottom" })
          .setLngLat([point.lng, point.lat])
          .setPopup(popup)
          .addTo(map);
      });

      if (points.length > 1) {
        map.fitBounds(bounds, { padding: 64, maxZoom: 14, duration: 0 });
      } else if (points.length === 1) {
        map.setCenter([points[0].lng, points[0].lat]);
        map.setZoom(13);
      }
    });

    return () => map.remove();
  }, [destination, points]);

  if (!destination) {
    return <div className="map-fallback"><strong>Map unavailable</strong><p>JOURNI did not return a destination location.</p></div>;
  }

  return <section className="map-panel">
    <div className="timeline-header">
      <div><span className="section-kicker">MAP VIEW{day ? ` · DAY ${day.day}` : ""}</span><h2>{day?.theme ?? "Planned locations"}</h2></div>
      <span className="map-count">{points.length} mapped {points.length === 1 ? "place" : "places"}</span>
    </div>
    <div className="maplibre-shell">
      <div className="maplibre-canvas" ref={container} role="application" aria-label="Map of itinerary stops" />
      {points.length === 0 && <div className="map-empty-overlay"><strong>No stop coordinates available</strong><span>The map is centered on the selected destination; no activity locations were estimated.</span></div>}
    </div>
    {mapError && <p className="map-error" role="status">{mapError}</p>}
    <p className="map-disclaimer">Dashed lines connect returned stop coordinates in schedule order; they are not road routes or turn-by-turn directions.</p>
    {points.length > 0 && <div className="map-stop-list">{points.map((point, index) => <div className="map-stop" key={`${point.name}-${point.time}-${index}`}>
      <span className={point.meal ? "meal" : ""}>{index + 1}</span><strong>{point.name}</strong><small>{point.time}</small>
    </div>)}</div>}
  </section>;
}
