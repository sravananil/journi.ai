import pandas as pd
import json
import uuid
import re
import os

RAW_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\geography\geolocations-indian-cities.csv"
OUT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\processed\cities.csv"
REPORT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\docs\CITY_NORMALIZATION_REPORT.md"

def normalize_text(text):
    if pd.isna(text):
        return None
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def main():
    if not os.path.exists(os.path.dirname(OUT_PATH)):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        
    df = pd.read_csv(RAW_PATH, encoding='latin-1')
    input_rows = len(df)
    
    # 1. Clean columns
    df.rename(columns={
        "Geoname ID": "geoname_id",
        "ASCII Name": "name",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Population": "population"
    }, inplace=True)
    
    # 2. Filter valid rows
    df = df.dropna(subset=['name', 'latitude', 'longitude'])
    missing_coords = input_rows - len(df)
    
    # 3. Create normalized names
    df['normalized_name'] = df['name'].apply(normalize_text)
    
    # 4. Deduplicate (keeping highest population)
    df = df.sort_values(by='population', ascending=False)
    df_dedup = df.drop_duplicates(subset=['normalized_name'], keep='first')
    dupes = len(df) - len(df_dedup)
    
    # 5. Format canonical output
    canonical = []
    for _, row in df_dedup.iterrows():
        raw_aliases = str(row.get('Alternate Names', ''))
        aliases = [normalize_text(a) for a in raw_aliases.split(',')] if raw_aliases and str(raw_aliases) != 'nan' else []
        aliases = [a for a in aliases if a and a != row['normalized_name']]
        
        canonical.append({
            "id": f"city_{row['geoname_id']}",
            "name": str(row['name']).strip(),
            "normalized_name": row['normalized_name'],
            "state": None, # Not available in this dataset
            "latitude": float(row['latitude']),
            "longitude": float(row['longitude']),
            "population": int(row['population']) if not pd.isna(row['population']) else 0,
            "aliases": json.dumps(list(set(aliases))),
            "source": "geolocations-indian-cities"
        })
        
    df_out = pd.DataFrame(canonical)
    df_out.to_csv(OUT_PATH, index=False, encoding='utf-8')
    
    # 6. Generate report
    report = f"""# City Normalization Report

## Summary
- Input rows: {input_rows}
- Rows rejected (missing coords/name): {missing_coords}
- Duplicates removed (by normalized name): {dupes}
- Canonical rows generated: {len(df_out)}

## Data Quality Rules Applied
- Read with `latin-1` encoding to handle legacy CSV.
- Deduplication: When multiple cities have the same normalized name, the one with the highest population is kept.
- State: Set to NULL as it is unavailable in this source dataset.
- Preserved original display names for `name`, created lowercase space-trimmed `normalized_name`.
"""
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"City normalization complete. Output: {len(df_out)} rows.")

if __name__ == "__main__":
    main()
