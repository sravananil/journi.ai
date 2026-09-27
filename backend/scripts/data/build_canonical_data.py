import os
import subprocess

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    print(f"--- Running {script_name} ---")
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    subprocess.run(["python", script_path], check=True)
    print()

def main():
    print("Starting canonical data build pipeline...\n")
    
    scripts = [
        "normalize_cities.py",
        "normalize_destinations.py",
        "normalize_places.py",
        "normalize_restaurants.py"
    ]
    
    for script in scripts:
        run_script(script)
        
    print("Build pipeline complete. Canonical CSVs generated in backend/data/processed/")

if __name__ == "__main__":
    main()
