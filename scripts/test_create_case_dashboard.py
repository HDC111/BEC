# scripts/auto_import_and_prepare_dashboard.py

import subprocess
import time
import os
import yaml
import psycopg2
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)

def import_dashboard(zip_path, username, password,env):
    print("📦 Importing dashboard from zip...")


    
    cmd = [
        "superset", "import-dashboards",
        "-p", zip_path,
        "--username", username
    ]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    try:
        stdout, stderr = process.communicate(input=password + "\n", timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        print("❌ Superset CLI timed out.")
        return False
    if process.returncode != 0:
        print("❌ Failed to import dashboard:")
        print(stderr)
        return False
    print("✅ Dashboard import completed.")
    return True

def get_dataset_id(config, table_name):
    session = requests.Session()
    login_url = "http://localhost:8088/login/"
    soup = BeautifulSoup(session.get(login_url).text, "html.parser")
    csrf_token_tag = soup.find("input", {"name": "csrf_token"})
    if not csrf_token_tag:
        raise ValueError("❌ Could not extract CSRF token.")
    csrf_token = csrf_token_tag["value"]

    login_payload = {
        "username": config["superset_admin"]["username"],
        "password": config["superset_admin"]["password"],
        "csrf_token": csrf_token
    }
    session.post(login_url, data=login_payload)
    csrf_cookie = session.cookies.get("csrf_token")
    headers = {
        "X-CSRFToken": csrf_cookie,
        "Referer": "http://localhost:8088/",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 🔎 Search for dataset by table_name
    resp = session.get(
        f"http://localhost:8088/api/v1/dataset/?q=(filters:!((col:table_name,opr:eq,value:{table_name})))",
        headers=headers
    )
    results = resp.json().get("result", [])
    if not results:
        raise ValueError(f"❌ Dataset '{table_name}' not found in Superset.")
    return results[0]["id"]

def clone_and_swap(config):
    pg_conf = config["postgres"]
    base_title = "MOCK"

    # ✅ Get case_name directly from config["paths"]["current_case"]
    case_path = Path(config["paths"]["current_case"])
    case_name = case_path.name  # e.g. 'case_20250717'
    new_title = f"{base_title}_{case_name}"
    target_table = f"{case_name}_marked_records"

    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()

    # === Get most recent dashboard named MOCK
    cur.execute("""
        SELECT id, json_metadata, position_json, css, slug, published
        FROM dashboards
        WHERE dashboard_title = %s
        ORDER BY changed_on DESC
        LIMIT 1
    """, (base_title,))
    row = cur.fetchone()
    if not row:
        raise ValueError("❌ Dashboard 'MOCK' not found after import.")
    old_dash_id, json_metadata, position_json, css, slug, published = row
    now = datetime.utcnow()

    # === Create cloned dashboard
    cur.execute("""
        INSERT INTO dashboards (
            dashboard_title, json_metadata, position_json, css, slug, published,
            created_on, changed_on
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        new_title, json_metadata, position_json, css,
        (slug + "_" + case_name) if slug else None,
        published, now, now
    ))
    new_dash_id = cur.fetchone()[0]
    print(f"✅ Cloned dashboard to '{new_title}' with ID: {new_dash_id}")

    # === Link charts
    cur.execute("SELECT slice_id FROM dashboard_slices WHERE dashboard_id = %s", (old_dash_id,))
    slice_ids = [row[0] for row in cur.fetchall()]
    for sid in slice_ids:
        cur.execute("INSERT INTO dashboard_slices (dashboard_id, slice_id) VALUES (%s, %s)", (new_dash_id, sid))
    print(f"🔗 Linked {len(slice_ids)} chart(s) to new dashboard.")

    # === Get dataset ID using Superset API
    dataset_id = get_dataset_id(config, target_table)
    print(f"✅ Dataset ID found: {dataset_id}")

    # === Swap dataset in charts
    for sid in slice_ids:
        cur.execute("UPDATE slices SET datasource_id = %s WHERE id = %s", (dataset_id, sid))
    print("🔄 Dataset swapped.")

    # === Fix chart params & datasource type
    cleaned = 0
    for sid in slice_ids:
        cur.execute("SELECT params, datasource_type FROM slices WHERE id = %s", (sid,))
        result = cur.fetchone()
        if not result:
            continue
        params, ds_type = result
        changed = False
        if params and "marked" in params:
            params = params.replace("marked", target_table)
            changed = True
        if ds_type != "table":
            cur.execute("UPDATE slices SET datasource_type = 'table' WHERE id = %s", (sid,))
            changed = True
        if changed:
            cur.execute("UPDATE slices SET params = %s WHERE id = %s", (params, sid))
            cleaned += 1
    print(f"🧼 Cleaned {cleaned} chart(s).")

    # === Fix dashboard layout filter references
    cur.execute("SELECT position_json FROM dashboards WHERE id = %s", (new_dash_id,))
    layout = cur.fetchone()[0]
    old_str = f"{old_dash_id}__table"
    new_str = f"{dataset_id}__table"
    if layout and old_str in layout:
        layout = layout.replace(old_str, new_str)
        cur.execute("UPDATE dashboards SET position_json = %s WHERE id = %s", (layout, new_dash_id))
        print(f"🎯 Layout filters updated: {old_str} → {new_str}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"🎉 Dashboard setup completed: {new_title}")

# === Main execution ===
if __name__ == "__main__":
    config = load_config()
    zip_path = config["paths"]["dashboard_zip"]
    username = config["superset_admin"]["username"]
    password = config["superset_admin"]["password"]

    if import_dashboard(zip_path, username, password):
        time.sleep(2)
        clone_and_swap(config)
