import pandas as pd
import uuid
import re
import os

RAW_SWIGGY = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\restaurants\swiggy_file.csv"
RAW_ZOMATO = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\raw\restaurants\zomato_dataset.csv"
OUT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\processed\restaurants.csv"
REPORT_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\docs\DATA_QUALITY_RULES.md" # We'll append

def normalize_text(text):
    if pd.isna(text):
        return None
    text = str(text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def parse_price(val):
    if pd.isna(val):
        return None
    val_str = str(val).lower()
    match = re.search(r'(\d+)', val_str)
    if match:
        return int(match.group(1))
    return None

def main():
    if not os.path.exists(os.path.dirname(OUT_PATH)):
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        
    df_swiggy = pd.read_csv(RAW_SWIGGY, encoding='utf-8')
    df_zomato = pd.read_csv(RAW_ZOMATO, encoding='utf-8')
    
    canonical = []
    
    # Process Swiggy (as base)
    for _, row in df_swiggy.iterrows():
        name = row.get("Restaurant Name")
        norm_name = normalize_text(name)
        city = row.get("Location")
        norm_city = normalize_text(city)
        area = row.get("Area")
        
        rating_val = row.get("Rating")
        rating = None
        if pd.notna(rating_val) and str(rating_val) not in ["--", "NEW"]:
            try:
                rating = float(rating_val)
            except ValueError:
                pass
                
        price = parse_price(row.get("Average Price"))
        price_level = None
        if price:
            if price <= 300: price_level = "budget"
            elif price <= 800: price_level = "moderate"
            else: price_level = "premium"
            
        record = {
            "id": f"rest_{uuid.uuid4().hex[:8]}",
            "name": name,
            "normalized_name": norm_name,
            "city": city,
            "area": area,
            "address": None,
            "cuisine": row.get("Cuisine"),
            "rating": rating,
            "rating_count": row.get("Number of Ratings"),
            "price_level": price_level,
            "cost": price,
            "is_pure_veg": True if str(row.get("Pure Veg")).strip().lower() == "yes" else False,
            "latitude": None,
            "longitude": None,
            "source": "swiggy_file.csv"
        }
        canonical.append(record)
        
    df_out = pd.DataFrame(canonical)
    
    # Deduplicate Swiggy self-duplicates
    df_out = df_out.drop_duplicates(subset=["normalized_name", "city", "area"], keep="first")
    
    df_out.to_csv(OUT_PATH, index=False, encoding='utf-8')
    print(f"Restaurants normalization complete. Output: {len(df_out)} rows.")

    report = """
## Restaurant Quality Rules
- Swiggy dataset `NEW` and `--` ratings are correctly mapped to `NULL`.
- Cost is extracted as integer from `Average Price` strings.
- Deduplication is conservative (by `normalized_name`, `city`, and `area`).
- Did not integrate Zomato in Phase 6C to avoid uncertain cross-dataset merging without lat/lon coordinates.
"""
    with open(REPORT_PATH, 'a', encoding='utf-8') as f:
        f.write(report)

if __name__ == "__main__":
    main()
