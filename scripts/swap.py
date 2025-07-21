# scripts/dataset_swap.py

import psycopg2
import yaml

def swap_dataset():
    with open("config/settings.yaml", "r") as f:
        settings = yaml.safe_load(f)

    pg_conf = settings["postgres"]
    dashboard_title_fragment = "MOCK"
    target_table = "case_20250717_marked_records"
    target_db_name = pg_conf["name"]

    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()

    # === Dashboard ID ===
    cur.execute("""
        SELECT id, dashboard_title FROM dashboards
        WHERE dashboard_title ILIKE %s
    """, (f"%{dashboard_title_fragment}%",))
    dash_result = cur.fetchone()
    if not dash_result:
        raise ValueError("❌ Dashboard not found.")
    dashboard_id, dashboard_title = dash_result
    print(f"📊 Found dashboard '{dashboard_title}' with ID: {dashboard_id}")

    # === Chart IDs ===
    cur.execute("""
        SELECT slice_id FROM dashboard_slices
        WHERE dashboard_id = %s
    """, (dashboard_id,))
    slice_ids = [row[0] for row in cur.fetchall()]
    print(f"🔍 Found {len(slice_ids)} chart(s) linked to this dashboard.")

    # === All Datasets ===
    print("\n🔍 Available datasets in Superset metadata:")
    cur.execute("""
        SELECT t.id, t.table_name, d.database_name
        FROM tables t
        JOIN dbs d ON t.database_id = d.id
        ORDER BY d.database_name, t.table_name
    """)
    for tid, table, dbname in cur.fetchall():
        print(f" - ID: {tid} | Dataset: '{table}' | DB: '{dbname}'")
    print("")

    # === New Dataset ID ===
    cur.execute("""
        SELECT t.id FROM tables t
        JOIN dbs d ON t.database_id = d.id
        WHERE t.table_name = %s AND d.database_name = %s
    """, (target_table, target_db_name))
    dataset_result = cur.fetchone()
    if not dataset_result:
        raise ValueError("❌ Target dataset not found.")
    dataset_id = dataset_result[0]
    print(f"✅ Target dataset ID for '{target_table}' in DB '{target_db_name}': {dataset_id}")

    # === Update Charts ===
    updated = 0
    for sid in slice_ids:
        cur.execute("UPDATE slices SET datasource_id = %s WHERE id = %s", (dataset_id, sid))
        updated += cur.rowcount
    print(f"✅ Updated {updated} chart(s) to use new dataset.")

    # === Update Dashboard Filters ===
    cur.execute("SELECT datasource_id FROM slices WHERE id = %s", (slice_ids[0],))
    old_id = cur.fetchone()[0]
    old_str = f"{old_id}__table"
    new_str = f"{dataset_id}__table"
    cur.execute("SELECT position_json FROM dashboards WHERE id = %s", (dashboard_id,))
    layout = cur.fetchone()[0]

    if layout and old_str in layout:
        new_layout = layout.replace(old_str, new_str)
        cur.execute("UPDATE dashboards SET position_json = %s WHERE id = %s", (new_layout, dashboard_id))
        print(f"✅ Replaced dashboard-level filters: '{old_str}' → '{new_str}'")
    else:
        print("ℹ️ No dashboard-level filters found or already correct.")

    # === Update Raw SQL in Charts ===
    from_table = "FROM public.marked"
    to_table = "FROM public.case_20250717_marked_records"
    updated_filters = 0
    for sid in slice_ids:
        cur.execute("SELECT params FROM slices WHERE id = %s", (sid,))
        result = cur.fetchone()
        if result and from_table in result[0]:
            new_params = result[0].replace(from_table, to_table)
            cur.execute("UPDATE slices SET params = %s WHERE id = %s", (new_params, sid))
            updated_filters += 1
    print(f"✅ Replaced raw SQL references in {updated_filters} chart(s).")

    # === Final Cleanup ===
    final_fix_count = 0
    for sid in slice_ids:
        cur.execute("SELECT params, datasource_type FROM slices WHERE id = %s", (sid,))
        result = cur.fetchone()
        if not result:
            continue
        old_params, ds_type = result
        changed = False
        if old_params:
            # Replace only exact match after staged renaming
            if "marked" in old_params:
                old_params = old_params.replace("marked", "case_20250717_marked_records")
                changed = True
        if ds_type != "table":
            cur.execute("UPDATE slices SET datasource_type = 'table' WHERE id = %s", (sid,))
            changed = True
        if changed:
            cur.execute("UPDATE slices SET params = %s WHERE id = %s", (old_params, sid))
            final_fix_count += 1

    print(f"✅ Final filter cleanup applied to {final_fix_count} chart(s).")
    conn.commit()
    cur.close()
    conn.close()
    print("🎉 Dataset swap complete.")
if __name__ == "__main__":
    swap_dataset()