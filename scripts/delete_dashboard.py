import psycopg2
import yaml

def delete_dashboard(title="MOCK_K"):
    with open("config/settings.yaml", "r") as f:
        settings = yaml.safe_load(f)

    pg_conf = settings["postgres"]
    conn = psycopg2.connect(
        dbname=pg_conf["db_name"],
        user=pg_conf["user"],
        password=pg_conf["password"],
        host=pg_conf["host"],
        port=pg_conf["port"]
    )
    cur = conn.cursor()

    # Get the dashboard ID
    cur.execute("SELECT id FROM dashboards WHERE dashboard_title = %s", (title,))
    row = cur.fetchone()
    if not row:
        print(f"❌ Dashboard '{title}' not found.")
        return

    dash_id = row[0]
    print(f"🗑️ Found dashboard '{title}' with ID: {dash_id}. Deleting...")

    # Delete from dashboard_slices
    cur.execute("DELETE FROM dashboard_slices WHERE dashboard_id = %s", (dash_id,))
    print(f"✅ Removed related entries from dashboard_slices.")

    # Delete from dashboards
    cur.execute("DELETE FROM dashboards WHERE id = %s", (dash_id,))
    print(f"✅ Deleted dashboard '{title}'.")

    conn.commit()
    cur.close()
    conn.close()
    print("🎉 Deletion complete.")

if __name__ == "__main__":
    delete_dashboard()
