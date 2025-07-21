import requests
import yaml
import sys
from sqlalchemy import create_engine, inspect
from bs4 import BeautifulSoup

def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)

def get_table_names(config):
    engine = create_engine(config["postgres"]["sqlalchemy_uri"])
    inspector = inspect(engine)
    return inspector.get_table_names(schema="public")

def create_superset_datasets(config, table_names):
    print("🔐 Logging into Superset...")

    session = requests.Session()
    login_url = "http://localhost:8088/login/"

    # Step 1: Visit login page to extract CSRF token
    login_page = session.get(login_url)
    soup = BeautifulSoup(login_page.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrf_token"})

    if not csrf_input:
        print("❌ Failed to extract CSRF token from login page.")
        sys.exit(1)

    csrf_token = csrf_input["value"]

    # Step 2: Submit login form
    login_payload = {
        "username": config["superset_admin"]["username"],
        "password": config["superset_admin"]["password"],
        "csrf_token": csrf_token
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": login_url
    }

    response = session.post(login_url, data=login_payload, headers=headers, allow_redirects=True)

    if "Welcome to Superset" not in response.text and "/superset/welcome" not in response.url:
        print("❌ Login failed or redirect missing. Response URL:", response.url)
        sys.exit(1)

    print("✅ Logged in successfully.")

    # Step 3: Get CSRF token from cookies (not always set as csrf_token, so fallback to manual extraction)
    csrf_cookie = session.cookies.get("csrf_token")
    if not csrf_cookie:
        print("❌ CSRF cookie not found. Trying fallback header.")
        csrf_cookie = csrf_token  # Use earlier token as fallback

    headers_json = {
        "X-CSRFToken": csrf_cookie,
        "Referer": "http://localhost:8088/",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Step 4: Get database ID
    db_resp = session.get("http://localhost:8088/api/v1/database/", headers=headers_json)
    dbs = db_resp.json()["result"]
    db_id = next((db["id"] for db in dbs if db["database_name"] == config["postgres"]["name"]), None)

    if not db_id:
        print("❌ Could not find Superset database.")
        sys.exit(1)

    # Step 5: Create datasets
    for table_name in table_names:
        payload = {
            "database": db_id,
            "schema": "public",
            "table_name": table_name
        }

        res = session.post("http://localhost:8088/api/v1/dataset/", json=payload, headers=headers_json)
        if res.status_code == 201:
            print(f"✅ Dataset created: {table_name}")
        elif res.status_code == 422 and "already exists" in res.text:
            print(f"⚠️ Dataset already exists: {table_name}")
        else:
            print(f"❌ Failed to create dataset for {table_name}: {res.text}")

if __name__ == "__main__":
    config = load_config()

    if len(sys.argv) < 2:
        print("❌ Please provide at least one table name.")
        sys.exit(1)

    table_names = sys.argv[1:]  # get passed-in table names
    create_superset_datasets(config, table_names)