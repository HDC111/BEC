import requests
import yaml
import sys
from bs4 import BeautifulSoup

def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)

def login_superset(config):
    session = requests.Session()
    login_url = "http://localhost:8088/login/"
    login_page = session.get(login_url)
    soup = BeautifulSoup(login_page.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrf_token"})

    if not csrf_input:
        print("❌ Failed to extract CSRF token.")
        sys.exit(1)

    csrf_token = csrf_input["value"]
    login_payload = {
        "username": config["superset_admin"]["username"],
        "password": config["superset_admin"]["password"],
        "csrf_token": csrf_token
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": login_url
    }

    response = session.post(login_url, data=login_payload, headers=headers)
    if "Welcome to Superset" not in response.text and "/superset/welcome" not in response.url:
        print("❌ Login failed.")
        sys.exit(1)

    csrf_cookie = session.cookies.get("csrf_token")
    print("✅ Logged in successfully.")
    return session, csrf_cookie

def get_dataset_id(session, csrf_token, dataset_name):
    headers = {
        "X-CSRFToken": csrf_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    resp = session.get(f"http://localhost:8088/api/v1/dataset/?q={dataset_name}", headers=headers)
    for ds in resp.json()["result"]:
        if ds["table_name"] == dataset_name:
            return ds["id"]
    return None

def get_dashboard_id(session, csrf_token, title_prefix):
    headers = {
        "X-CSRFToken": csrf_token,
        "Accept": "application/json"
    }
    resp = session.get("http://localhost:8088/api/v1/dashboard/", headers=headers)
    for dash in resp.json()["result"]:
        if dash["dashboard_title"].startswith(title_prefix):
            return dash["id"]
    return None

def get_chart_ids_from_dashboard(session, csrf_token, dashboard_id):
    headers = {
        "X-CSRFToken": csrf_token,
        "Accept": "application/json"
    }
    resp = session.get(f"http://localhost:8088/api/v1/dashboard/{dashboard_id}", headers=headers)
    return resp.json()["result"]["charts"]

def update_chart_dataset(session, csrf_token, chart_id, new_dataset_id):
    headers = {
        "X-CSRFToken": csrf_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    resp = session.get(f"http://localhost:8088/api/v1/chart/{chart_id}", headers=headers)
    chart_data = resp.json()["result"]
    chart_data["dataset_id"] = new_dataset_id

    update = session.put(f"http://localhost:8088/api/v1/chart/{chart_id}", json=chart_data, headers=headers)
    return update.status_code == 200

def main():
    config = load_config()
    session, csrf_token = login_superset(config)

    dashboard_prefix = "MOCK_"
    target_dataset = "marked_records"  # 👈 Final dataset to switch to

    # Get dataset ID
    new_dataset_id = get_dataset_id(session, csrf_token, target_dataset)
    if not new_dataset_id:
        print(f"❌ Dataset '{target_dataset}' not found.")
        return

    # Get dashboard ID
    dash_id = get_dashboard_id(session, csrf_token, dashboard_prefix)
    if not dash_id:
        print(f"❌ Dashboard starting with '{dashboard_prefix}' not found.")
        return

    # Get charts
    chart_ids = get_chart_ids_from_dashboard(session, csrf_token, dash_id)
    print(f"🔄 Swapping {len(chart_ids)} chart(s) to use dataset '{target_dataset}'...")

    # Update charts
    success = 0
    for cid in chart_ids:
        if update_chart_dataset(session, csrf_token, cid, new_dataset_id):
            print(f"✅ Chart {cid} updated.")
            success += 1
        else:
            print(f"❌ Failed to update chart {cid}.")

    print(f"\n🎯 Done: {success}/{len(chart_ids)} charts updated to dataset '{target_dataset}'.")

if __name__ == "__main__":
    main()
