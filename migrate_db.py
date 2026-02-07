import sqlite3
import os

db_path = "monitor.db"

def migrate():
    if not os.path.exists(db_path):
        print("Database file not found. It will be created by the app.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("perf_score", "FLOAT"),
        ("perf_fcp", "FLOAT"),
        ("perf_lcp", "FLOAT"),
        ("perf_cls", "FLOAT"),
        ("perf_seo", "FLOAT"),
        ("perf_accessible", "FLOAT"),
        ("perf_best_practices", "FLOAT"),
        ("perf_details", "JSON"),
        ("perf_screenshot", "TEXT"),
        ("perf_tbt", "FLOAT")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE monitors ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added column {col_name}")
        except sqlite3.OperationalError:
            print(f"ℹ️ Column {col_name} already exists or error occurred.")
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
