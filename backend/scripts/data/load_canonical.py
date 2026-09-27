import sqlite3
import pandas as pd
import os
import shutil

DB_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\journi.db"
BACKUP_PATH = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\journi.db.backup_phase6c"
PROCESSED_DIR = r"c:\Users\ANIL KUMAR\OneDrive\Desktop\journi\backend\data\processed"

def backup_db():
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"Created backup at {BACKUP_PATH}")
    else:
        print("Backup already exists.")

def load_table(conn, table_name, csv_file, append_mode=False):
    csv_path = os.path.join(PROCESSED_DIR, csv_file)
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return
        
    df = pd.read_csv(csv_path, encoding='utf-8')
    
    # We must ensure we create tables if they don't exist, using Pandas to_sql
    # To be idempotent and safe, we can use a transaction
    try:
        if append_mode:
            # For places, delete previously inserted canonical rows (idempotent), but KEEP "JOURNI Curated"
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {table_name} WHERE source != 'JOURNI Curated'")
            
            if 'normalized_name' in df.columns and table_name == 'places':
                df = df.drop(columns=['normalized_name'])
                
            # Now append the new canonical rows
            df.to_sql(table_name, conn, if_exists='append', index=False)
            print(f"Appended {len(df)} rows to {table_name}")
        else:
            # For new tables, we can just replace
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"Replaced {table_name} with {len(df)} rows")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to load {table_name}: {e}")
        raise e

def main():
    backup_db()
    
    # Must use python sqlite3 to have control over transactions
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Load tables
        load_table(conn, "cities", "cities.csv", append_mode=False)
        load_table(conn, "destinations", "destinations.csv", append_mode=False)
        load_table(conn, "restaurants", "restaurants.csv", append_mode=False)
        load_table(conn, "places", "places.csv", append_mode=True)
        
        conn.commit()
        print("Database load completed successfully.")
    except Exception as e:
        conn.rollback()
        print("Database load failed, rolled back transaction.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
