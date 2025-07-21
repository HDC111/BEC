# scripts/clone_dashboard_with_filters.py

import psycopg2
import yaml
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)

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

    resp = session.get(
        f"http://localhost:8088/api/v1/dataset/?q=(filters:!((col:table_name,opr:eq,value:{table_name})))",
        headers=headers
    )
    results = resp.json().get("result", [])
    if not results:
        raise ValueError(f"❌ Dataset '{table_name}' not found in Superset.")
    return results[0]["id"]

def recursively_replace_chart_ids(layout_json, id_map):
    if isinstance(layout_json, dict):
        for k, v in layout_json.items():
            if k == "meta" and "chartId" in v and v["chartId"] in id_map:
                v["chartId"] = id_map[v["chartId"]]
            elif isinstance(v, (dict, list)):
                layout_json[k] = recursively_replace_chart_ids(v, id_map)
    elif isinstance(layout_json, list):
        return [recursively_replace_chart_ids(i, id_map) for i in layout_json]
    return layout_json

def clone_dashboard_with_chart_and_filter_swap():
    config = load_config()
    pg_conf = config["postgres"]
    base_title = "MOCK"
    case_path = Path(config["paths"]["current_case"])
    case_name = case_path.name
    dashboard_title = f"{base_title}_{case_name}"
    old_table = "marked"
    new_table = f"{case_name}_marked_records"
    db_name = pg_conf["name"]

    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()

    # Get original dashboard
    cur.execute("""
        SELECT id, position_json, json_metadata, css, slug, published
        FROM dashboards
        WHERE dashboard_title = %s
        ORDER BY changed_on DESC LIMIT 1
    """, (base_title,))
    row = cur.fetchone()
    if not row:
        raise Exception("Dashboard 'MOCK' not found.")
    old_dash_id, position_json, json_metadata, css, slug, published = row

    # Get original charts
    cur.execute("SELECT slice_id FROM dashboard_slices WHERE dashboard_id = %s", (old_dash_id,))
    old_chart_ids = [r[0] for r in cur.fetchall()]

    # Get dataset ID for new table
    new_dataset_id = get_dataset_id(config, new_table)

    # Clone charts
    chart_id_map = {}
    for old_id in old_chart_ids:
        cur.execute("SELECT slice_name, viz_type, params, datasource_type FROM slices WHERE id = %s", (old_id,))
        slice_name, viz_type, params, datasource_type = cur.fetchone()
        now = datetime.utcnow()

        # Replace old table name in chart params
        if params and old_table in params:
            params = params.replace(old_table, new_table)

        cur.execute("""
            INSERT INTO slices (slice_name, viz_type, params, datasource_id, datasource_type, created_on, changed_on)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (f"{slice_name} ({case_name})", viz_type, params, new_dataset_id, datasource_type, now, now))
        new_id = cur.fetchone()[0]
        chart_id_map[old_id] = new_id
    print(f"✅ Cloned {len(chart_id_map)} charts.")

    # Replace chart IDs in layout
    layout = json.loads(position_json)
    updated_layout = json.dumps(recursively_replace_chart_ids(layout, chart_id_map))

    # Replace datasetId in filter configuration
    metadata = json.loads(json_metadata) if json_metadata else {}
    filters = metadata.get("native_filter_configuration", [])
    for f in filters:
        for target in f.get("targets", []):
            old_id = target.get("datasetId")
            target["datasetId"] = new_dataset_id
    metadata["native_filter_configuration"] = filters
    updated_metadata = json.dumps(metadata)

    # Insert new dashboard
    now = datetime.utcnow()
    cur.execute("""
        INSERT INTO dashboards (dashboard_title, json_metadata, position_json, css, slug, published, created_on, changed_on)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        dashboard_title, updated_metadata, updated_layout, css,
        (slug + "_" + case_name) if slug else None,
        published, now, now
    ))
    new_dash_id = cur.fetchone()[0]

    for new_chart_id in chart_id_map.values():
        cur.execute("INSERT INTO dashboard_slices (dashboard_id, slice_id) VALUES (%s, %s)", (new_dash_id, new_chart_id))

    conn.commit()
    cur.close()
    conn.close()
    print(f"🎉 Dashboard and filters fully cloned: '{dashboard_title}'")

if __name__ == "__main__":
    clone_dashboard_with_chart_and_filter_swap()
