import pandas as pd
import json
import uuid
import re
import os

RAW_JSON = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\attractions\india_tourism_dataset.json"
RAW_CSV = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\attractions\holidify.csv"
OUT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\processed\destinations.csv"
REPORT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\docs\DATA_QUALITY_RULES.md" # Will append or write part of it here

def normalize_text(text):
    if not text:
        return None
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def main():
    if not os.path.exists(os.path.dirname(OUT_PATH)):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        
    with open(RAW_JSON, 'r', encoding='utf-8') as f:
        tourism_data = json.load(f)
        
    df_holidify = pd.read_csv(RAW_CSV, encoding='utf-8')
    df_holidify['normalized_name'] = df_holidify['City'].apply(normalize_text)
    df_holidify = df_holidify.drop_duplicates(subset=['normalized_name'], keep='first')
    holidify_map = df_holidify.set_index('normalized_name').to_dict('index')
    
    canonical = []
    
    for dest in tourism_data:
        name = dest.get("destination_name")
        norm_name = normalize_text(name)
        
        # Base data
        record = {
            "id": dest.get("id") or f"dest_{uuid.uuid4().hex[:8]}",
            "name": name,
            "normalized_name": norm_name,
            "state": dest.get("state"),
            "district": dest.get("district"),
            "region": dest.get("region"),
            "latitude": dest.get("coordinates", {}).get("latitude"),
            "longitude": dest.get("coordinates", {}).get("longitude"),
            "altitude_m": dest.get("altitude_m"),
            "popularity_score": dest.get("popularity_score"),
            "accessibility": dest.get("accessibility"),
            "nearest_airport": json.dumps(dest.get("nearest_airport")) if dest.get("nearest_airport") else None,
            "nearest_railway_station": json.dumps(dest.get("nearest_railway_station")) if dest.get("nearest_railway_station") else None,
            "nearest_major_city": json.dumps(dest.get("nearest_major_city")) if dest.get("nearest_major_city") else None,
            "road_connectivity": dest.get("road_connectivity"),
            "budget_daily_low": dest.get("budget_category", {}).get("total_daily_range", [None, None])[0],
            "budget_daily_high": dest.get("budget_category", {}).get("total_daily_range", [None, None])[1],
            "midrange_daily_low": dest.get("mid_range_category", {}).get("total_daily_range", [None, None])[0],
            "midrange_daily_high": dest.get("mid_range_category", {}).get("total_daily_range", [None, None])[1],
            "luxury_daily_low": dest.get("luxury_category", {}).get("total_daily_range", [None, None])[0],
            "luxury_daily_high": dest.get("luxury_category", {}).get("total_daily_range", [None, None])[1],
            "trip_types": json.dumps(dest.get("trip_types", [])),
            "activities_available": json.dumps(dest.get("activities_available", [])),
            "best_seasons": json.dumps(dest.get("best_seasons", [])),
            "ideal_for": json.dumps(dest.get("ideal_for", [])),
            "minimum_days": dest.get("minimum_days"),
            "ideal_days": dest.get("ideal_days"),
            "maximum_days": dest.get("maximum_days"),
            "food_scene": dest.get("food_scene"),
            "local_cuisine": json.dumps(dest.get("local_cuisine_must_try", [])),
            "description": None,
            "source": "india_tourism_dataset.json"
        }
        
        # Enrich from Holidify
        if norm_name in holidify_map:
            h_data = holidify_map[norm_name]
            record["description"] = h_data.get("About the city")
            record["source"] = "india_tourism_dataset.json,holidify.csv"
            
        canonical.append(record)
        
    df_out = pd.DataFrame(canonical)
    df_out.to_csv(OUT_PATH, index=False, encoding='utf-8')
    print(f"Destination normalization complete. Output: {len(df_out)} rows.")

if __name__ == "__main__":
    main()
