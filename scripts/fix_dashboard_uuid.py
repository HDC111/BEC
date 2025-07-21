import os
import zipfile
import yaml
import uuid
import shutil
import psycopg2
from pathlib import Path

# === Load settings.yaml ===
import yaml as yamlloader

with open("config/settings.yaml", "r") as f:
    config = yamlloader.safe_load(f)

export_zip = config["paths"]["dashboard_zip"]
fixed_zip = config["paths"]["fixed_dashboard_zip"]

working_dir = "temp_dashboard_edit"

pg_conf = config["postgres"]
target_db = pg_conf["name"]
target_table = "marked_records"

# === Step 1: Get dataset UUID from Superset metadata DB ===
def get_dataset_uuid():
    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT t.uuid
        FROM tables t
        JOIN dbs d ON t.database_id = d.id
        WHERE t.table_name = %s AND d.database_name = %s
    """, (target_table, target_db))
    result = cur.fetchone()
    cur.close()
    conn.close()
    if not result:
        raise ValueError(f"Dataset '{target_table}' in database '{target_db}' not found.")
    return str(result[0])

# === Step 2: Unzip export ===
def unzip_export(zip_path, extract_to):
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

# === Step 3: Replace dataset_uuid in chart YAMLs ===
def update_dataset_uuid(charts_dir, new_uuid):
    updated = []
    for fname in os.listdir(charts_dir):
        if fname.endswith(".yaml"):
            path = os.path.join(charts_dir, fname)
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            if "dataset_uuid" in data:
                data["dataset_uuid"] = new_uuid
                with open(path, "w") as f:
                    yaml.dump(data, f, sort_keys=False)
                updated.append(fname)
    return updated

# === Step 4: Re-zip ===
def rezip_folder(folder_path, output_zip):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, rel_path)

# === MAIN ===
if __name__ == "__main__":
    print("🔍 Fetching dataset UUID...")
    uuid = get_dataset_uuid()
    print(f"✅ Found dataset UUID: {uuid}")

    print("📦 Unzipping export...")
    unzip_export(export_zip, working_dir)

    charts_folder = os.path.join(working_dir, "dashboard_export_20250703T171322", "charts")

    if not os.path.exists(charts_folder):
        raise FileNotFoundError("charts/ folder not found in the export zip.")

    print("🛠 Updating chart dataset UUIDs...")
    updated_files = update_dataset_uuid(charts_folder, uuid)

    print(f"✅ Updated {len(updated_files)} chart files.")

    print("🗜 Creating fixed ZIP...")
    rezip_folder(working_dir, fixed_zip)

    print(f"✅ All done! Fixed dashboard bundle saved to:\n{fixed_zip}")
