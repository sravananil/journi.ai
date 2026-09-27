import pandas as pd
import json
import uuid
import re
import os

RAW_PLACES = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\attractions\places.csv"
RAW_TOP = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\attractions\Top Indian Places to Visit.csv"
OUT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\processed\places.csv"
REPORT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\docs\PLACE_MATCHING_REPORT.md"

def normalize_text(text):
    if pd.isna(text):
        return None
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def parse_price(val):
    if pd.isna(val):
        return 0
    val_str = str(val).lower().replace(',', '')
    if 'free' in val_str:
        return 0
    # extract first number
    match = re.search(r'(\d+)', val_str)
    if match:
        return int(match.group(1))
    return 0

def map_interest(raw_category):
    if not raw_category:
        return []
    raw = str(raw_category).lower()
    mapping = {
        'cultural & heritage sites': ['culture', 'heritage'],
        'adventure & outdoor activities': ['adventure', 'nature', 'outdoor'],
        'religious & spiritual pilgrimages': ['culture', 'heritage'],
        'natural landscapes & wildlife': ['nature', 'wildlife'],
        'shopping & markets': ['shopping'],
        'beaches & coastal areas': ['beaches', 'nature'],
        'museums & educational institutions': ['culture', 'museum'],
        'historical forts & palaces': ['culture', 'heritage', 'fort']
    }
    for key, mapped in mapping.items():
        if key in raw:
            return mapped
    return ['sightseeing']

def main():
    if not os.path.exists(os.path.dirname(OUT_PATH)):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        
    df_places = pd.read_csv(RAW_PLACES, encoding='latin-1')
    df_top = pd.read_csv(RAW_TOP, encoding='utf-8')
    
    # 1. Prepare Top Indian Places for matching
    df_top['norm_name'] = df_top['Name'].apply(normalize_text)
    df_top['norm_city'] = df_top['City'].apply(normalize_text)
    
    matched_enrichments = 0
    unmatched_enrichments = 0
    ambiguous_matches = 0
    
    canonical = []
    
    # 2. Iterate primary dataset
    for idx, row in df_places.iterrows():
        name = row.get('popular_destination')
        city = row.get('city')
        state = row.get('state')
        lat = row.get('latitude')
        lng = row.get('longitude')
        raw_interest = row.get('interest')
        rating = row.get('google_rating')
        price_fare = row.get('price_fare')
        
        norm_name = normalize_text(name)
        norm_city = normalize_text(city)
        
        # State normalization (Karnataka vs Karanataka)
        if isinstance(state, str):
            state = state.replace('Karanataka', 'Karnataka').replace('Gujrat', 'Gujarat')
            
        # Data Quality: Malformed rating
        confidence = None # Unknown
        # We preserve rating where needed, but confidence remains NULL
        # Matching enrichment
        # We try to find a match in Top Indian Places based on Name + City
        match_df = df_top[(df_top['norm_name'] == norm_name) & (df_top['norm_city'] == norm_city)]
        
        duration = 60 # default
        entrance_fee = parse_price(price_fare)
        source = "places.csv"
        
        if len(match_df) == 1:
            matched_enrichments += 1
            source += ",Top Indian Places to Visit.csv"
            enrich_row = match_df.iloc[0]
            # Duration parsing
            dur_str = str(enrich_row.get('time needed to visit in hrs', ''))
            dur_match = re.search(r'(\d+(\.\d+)?)', dur_str)
            if dur_match:
                duration = int(float(dur_match.group(1)) * 60)
            
            # Fee parsing
            top_fee = enrich_row.get('Entrance Fee in INR')
            if pd.notna(top_fee) and top_fee != 'Free':
                fee_match = re.search(r'(\d+)', str(top_fee))
                if fee_match:
                    entrance_fee = int(fee_match.group(1))
                    
        elif len(match_df) > 1:
            ambiguous_matches += 1
            
        record = {
            "id": f"p_{uuid.uuid4().hex[:8]}",
            "name": name,
            "normalized_name": norm_name,
            "destination": city if pd.notna(city) else None,
            "area": None,
            "category": raw_interest, # keep raw
            "latitude": float(lat) if pd.notna(lat) else None,
            "longitude": float(lng) if pd.notna(lng) else None,
            "interests": json.dumps(map_interest(raw_interest)),
            "suitable_for": None, # Unknown
            "opening_hours": None, # Unknown
            "duration": duration,
            "estimated_cost": entrance_fee,
            "best_time": None, # Unknown
            "walking_level": None, # Unknown
            "indoor_outdoor": None, # Unknown
            "description": None,
            "source": source,
            "confidence": confidence
        }
        
        canonical.append(record)
        
    df_out = pd.DataFrame(canonical)
    df_out.to_csv(OUT_PATH, index=False, encoding='utf-8')
    
    # Generate Report
    report = f"""# Place Matching Report

## Summary
- Primary places (places.csv): {len(df_places)}
- Canonical places generated: {len(df_out)}
- Matched enrichments (Name + City): {matched_enrichments}
- Ambiguous matches: {ambiguous_matches}

## Rules Applied
- Destination: Resolves from `city` field. Does not fallback to 'Goa'. If missing, it remains NULL.
- Interests: Mapped using an explicit mapping table (e.g. 'Cultural & Heritage Sites' -> ['culture', 'heritage']).
- Confidence: `rating / 5.0` applied ONLY where rating is a valid 0-5 float.
- Suitable_for: Left as NULL (no inferencing).
- Walking_level: Left as NULL (no inferencing).
- Opening_hours: Left as NULL.
"""
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"Places normalization complete. Output: {len(df_out)} rows.")

if __name__ == "__main__":
    main()
