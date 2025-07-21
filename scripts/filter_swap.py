# scripts/filter_swap_decoupled.py

import psycopg2
import yaml
import json
from pathlib import Path

def swap_filter_target_decoupled():
    with open("config/settings.yaml", "r") as f:
        settings = yaml.safe_load(f)

    pg_conf = settings["postgres"]
    base_title = "MOCK"
    case_path = Path(settings["paths"]["current_case"])
    case_name = case_path.name
    dashboard_title_fragment = f"{base_title}_{case_name}"
    target_table = f"{case_name}_marked_records"
    target_db_name = pg_conf["name"]

    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()

    # === Step 1: Find the cloned dashboard
    cur.execute("""
        SELECT id, json_metadata FROM dashboards
        WHERE dashboard_title = %s
        ORDER BY changed_on DESC
        LIMIT 1
    """, (dashboard_title_fragment,))
    result = cur.fetchone()
    if not result:
        raise ValueError(f"❌ Dashboard '{dashboard_title_fragment}' not found.")
    dashboard_id, json_metadata = result
    print(f"📊 Found dashboard ID: {dashboard_id}")

    # === Step 2: Find the new dataset ID
    cur.execute("""
        SELECT t.id FROM tables t
        JOIN dbs d ON t.database_id = d.id
        WHERE t.table_name = %s AND d.database_name = %s
    """, (target_table, target_db_name))
    dataset_result = cur.fetchone()
    if not dataset_result:
        raise ValueError(f"❌ Dataset '{target_table}' not found.")
    target_dataset_id = dataset_result[0]
    print(f"✅ Target dataset ID: {target_dataset_id}")

    # === Step 3: Update native filter targets in json_metadata
    if not json_metadata:
        print("⚠️ No json_metadata found.")
        cur.close()
        conn.close()
        return

    meta = json.loads(json_metadata)
    filters = meta.get("native_filter_configuration", [])
    if not filters:
        print("⚠️ No native filters found.")
    else:
        updated = 0
        for f in filters:
            for target in f.get("targets", []):
                old_id = target.get("datasetId")
                target["datasetId"] = target_dataset_id
                updated += 1
        meta["native_filter_configuration"] = filters

        new_metadata = json.dumps(meta)
        cur.execute("""
            UPDATE dashboards
            SET json_metadata = %s
            WHERE id = %s
        """, (new_metadata, dashboard_id))
        print(f"✅ Updated {updated} filter target(s) in json_metadata.")

    conn.commit()
    cur.close()
    conn.close()
    print("🎉 Filter target swap completed.")

if __name__ == "__main__":
    swap_filter_target_decoupled()
