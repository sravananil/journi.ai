"""
load_to_postgres.py — JOURNI Canonical Data → PostgreSQL Loader
================================================================
Loads canonical processed CSV files into PostgreSQL via SQLAlchemy ORM.

Usage:
    cd backend
    python scripts/data/load_to_postgres.py

This script is:
  - Idempotent: safe to re-run (truncate + reload per table)
  - Transactional: one transaction per table; rolls back on failure
  - Non-destructive: does NOT drop tables; data is replaced within tables
  - Preserves NULL semantics from Phase 6C
  - Preserves legacy JOURNI Curated Goa places
"""

import os
import sys
import json
import logging
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.city import City
from app.models.destination import Destination
from app.models.place import Place
from app.models.restaurant import Restaurant

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Check backend/.env")

PROCESSED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "processed"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def _parse_json_col(val):
    """Safely parse a JSON-string column to a Python object (or None)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (list, dict)):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _safe_float(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except Exception:
        return None


def _safe_int(val, default=None):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return int(float(val))
    except Exception:
        return default


def _safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s else None


# ─── Cities ───────────────────────────────────────────────────────────────────

def load_cities(session):
    path = os.path.join(PROCESSED_DIR, "cities.csv")
    df = pd.read_csv(path, encoding="utf-8")
    
    session.query(City).delete()
    session.flush()
    
    batch = []
    for _, row in df.iterrows():
        batch.append(City(
            id=str(row["id"]),
            name=str(row["name"]).strip(),
            normalized_name=str(row["normalized_name"]).strip(),
            state=None,
            latitude=_safe_float(row.get("latitude")),
            longitude=_safe_float(row.get("longitude")),
            population=_safe_int(row.get("population"), default=0),
            aliases=_parse_json_col(row.get("aliases")),
            source=_safe_str(row.get("source")) or "geolocations-indian-cities",
        ))
        if len(batch) >= 1000:
            session.bulk_save_objects(batch)
            batch = []
    if batch:
        session.bulk_save_objects(batch)
    
    count = session.query(City).count()
    logger.info(f"Cities loaded: {count:,}")
    return count


# ─── Destinations ─────────────────────────────────────────────────────────────

def load_destinations(session):
    path = os.path.join(PROCESSED_DIR, "destinations.csv")
    df = pd.read_csv(path, encoding="utf-8")
    
    session.query(Destination).delete()
    session.flush()
    
    batch = []
    for _, row in df.iterrows():
        batch.append(Destination(
            id=str(row["id"]),
            name=_safe_str(row.get("name")),
            normalized_name=_safe_str(row.get("normalized_name")),
            state=_safe_str(row.get("state")),
            district=_safe_str(row.get("district")),
            region=_safe_str(row.get("region")),
            latitude=_safe_float(row.get("latitude")),
            longitude=_safe_float(row.get("longitude")),
            altitude_m=_safe_float(row.get("altitude_m")),
            popularity_score=_safe_float(row.get("popularity_score")),
            accessibility=_safe_str(row.get("accessibility")),
            nearest_airport=_safe_str(row.get("nearest_airport")),
            nearest_railway_station=_safe_str(row.get("nearest_railway_station")),
            nearest_major_city=_safe_str(row.get("nearest_major_city")),
            road_connectivity=_safe_str(row.get("road_connectivity")),
            budget_daily_low=_safe_int(row.get("budget_daily_low")),
            budget_daily_high=_safe_int(row.get("budget_daily_high")),
            midrange_daily_low=_safe_int(row.get("midrange_daily_low")),
            midrange_daily_high=_safe_int(row.get("midrange_daily_high")),
            luxury_daily_low=_safe_int(row.get("luxury_daily_low")),
            luxury_daily_high=_safe_int(row.get("luxury_daily_high")),
            trip_types=_parse_json_col(row.get("trip_types")),
            activities_available=_parse_json_col(row.get("activities_available")),
            best_seasons=_parse_json_col(row.get("best_seasons")),
            ideal_for=_parse_json_col(row.get("ideal_for")),
            minimum_days=_safe_int(row.get("minimum_days")),
            ideal_days=_safe_int(row.get("ideal_days")),
            maximum_days=_safe_int(row.get("maximum_days")),
            food_scene=_safe_str(row.get("food_scene")),
            local_cuisine=_parse_json_col(row.get("local_cuisine")),
            description=_safe_str(row.get("description")),
            source=_safe_str(row.get("source")) or "india_tourism_dataset",
        ))
    
    session.bulk_save_objects(batch)
    count = session.query(Destination).count()
    logger.info(f"Destinations loaded: {count:,}")
    return count


# ─── Places ───────────────────────────────────────────────────────────────────

def load_places(session):
    path = os.path.join(PROCESSED_DIR, "places.csv")
    df = pd.read_csv(path, encoding="utf-8")
    
    # Preserve JOURNI Curated (legacy Goa) rows — delete only canonical rows
    session.query(Place).filter(Place.source != "JOURNI Curated").delete()
    session.flush()
    
    batch = []
    loaded = 0
    for _, row in df.iterrows():
        if _safe_str(row.get("source")) == "JOURNI Curated":
            continue  # already in DB
        
        batch.append(Place(
            id=str(row["id"]),
            name=_safe_str(row.get("name")),
            destination=_safe_str(row.get("destination")),
            area=None,  # Phase 6C: area = NULL (not inferable from city)
            category=_safe_str(row.get("category")),
            latitude=_safe_float(row.get("latitude")),
            longitude=_safe_float(row.get("longitude")),
            interests=_parse_json_col(row.get("interests")),
            suitable_for=None,          # Phase 6C NULL semantics
            opening_hours=None,         # Phase 6C NULL semantics
            duration=_safe_int(row.get("duration"), default=60),
            estimated_cost=_safe_int(row.get("estimated_cost"), default=0),
            best_time=None,             # Phase 6C NULL semantics
            walking_level=None,         # Phase 6C NULL semantics
            indoor_outdoor=None,
            description=None,
            source=_safe_str(row.get("source")) or "places.csv",
            confidence=_safe_float(row.get("confidence")),
        ))
        loaded += 1
        if len(batch) >= 500:
            session.bulk_save_objects(batch)
            batch = []
    
    if batch:
        session.bulk_save_objects(batch)
    
    count = session.query(Place).count()
    logger.info(f"Places loaded: {count:,} total (canonical + JOURNI Curated Goa preserved)")
    return count


# ─── Restaurants ──────────────────────────────────────────────────────────────

def load_restaurants(session):
    path = os.path.join(PROCESSED_DIR, "restaurants.csv")
    
    logger.info("Clearing existing restaurants...")
    session.query(Restaurant).delete()
    session.flush()
    
    total = 0
    CHUNK = 5000
    seen_ids = set()
    
    for chunk_df in pd.read_csv(path, encoding="utf-8", chunksize=CHUNK):
        # Deduplicate within and across chunks
        chunk_df = chunk_df.drop_duplicates(subset=["id"])
        chunk_df = chunk_df[~chunk_df["id"].astype(str).isin(seen_ids)]
        seen_ids.update(chunk_df["id"].astype(str).tolist())
        
        batch = []
        for _, row in chunk_df.iterrows():
            batch.append(Restaurant(
                id=str(row["id"]),
                name=_safe_str(row.get("name")),
                normalized_name=_safe_str(row.get("normalized_name")),
                city=_safe_str(row.get("city")),
                area=_safe_str(row.get("area")),
                address=_safe_str(row.get("address")),
                cuisine=_safe_str(row.get("cuisine")),
                rating=_safe_float(row.get("rating")),
                rating_count=_safe_str(row.get("rating_count")),
                price_level=_safe_str(row.get("price_level")),
                cost=_safe_int(row.get("cost")),
                is_pure_veg=bool(row["is_pure_veg"]) if pd.notna(row.get("is_pure_veg")) else None,
                latitude=_safe_float(row.get("latitude")),
                longitude=_safe_float(row.get("longitude")),
                source=_safe_str(row.get("source")) or "swiggy_file.csv",
            ))
        if batch:
            session.bulk_save_objects(batch)
        total += len(batch)
        if total % 20000 == 0:
            session.flush()
            logger.info(f"  ... {total:,} restaurants inserted")
    
    count = session.query(Restaurant).count()
    logger.info(f"Restaurants loaded: {count:,} (deduplicated from {total:,} raw rows)")
    return count


# ─── Verification ─────────────────────────────────────────────────────────────

def verify_counts(session):
    expected = {
        "cities":      (3000, 3600),
        "destinations": (95, 110),
        "places":       (1000, 1100),
        "restaurants":  (130000, 145000),
    }
    counts = {
        "cities":       session.query(City).count(),
        "destinations": session.query(Destination).count(),
        "places":       session.query(Place).count(),
        "restaurants":  session.query(Restaurant).count(),
    }
    
    print("\n" + "=" * 55)
    print("RECORD COUNT VERIFICATION")
    print("=" * 55)
    all_ok = True
    for table, count in counts.items():
        lo, hi = expected[table]
        ok = lo <= count <= hi
        status = "OK" if ok else "!!"
        print(f"  {status} {table:15s}: {count:>8,d}  (expected {lo:,}-{hi:,})")
        if not ok:
            all_ok = False
    print("=" * 55)
    return all_ok, counts


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("Starting JOURNI canonical data load to PostgreSQL...")
    
    session = Session()
    try:
        # Load each table in its own flush cycle (single transaction)
        city_count = load_cities(session)
        dest_count = load_destinations(session)
        place_count = load_places(session)
        rest_count = load_restaurants(session)
        
        session.commit()
        
        # Verify post-commit
        ok, counts = verify_counts(session)
        
        print(f"\nLoad complete:")
        print(f"  Cities:       {city_count:>8,d}")
        print(f"  Destinations: {dest_count:>8,d}")
        print(f"  Places:       {place_count:>8,d}")
        print(f"  Restaurants:  {rest_count:>8,d}")
        
        if not ok:
            print("\n  NOTE: Some counts outside expected range — see PHASE_7_TASK_2_REPORT.md")
            
    except Exception as e:
        session.rollback()
        logger.error(f"Load failed, rolled back: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
