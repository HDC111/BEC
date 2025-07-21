import subprocess
import os
import yaml
import glob

def load_config(path="config/settings.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_latest_dashboard_zips(folder="superset_exports", count=1):
    """
    Return the latest 'count' number of dashboard zip file paths from the given folder.
    """
    zips = glob.glob(os.path.join(folder, "*.zip"))
    zips.sort(key=os.path.getctime, reverse=True)  # Newest first
    return zips[:count] if count else zips

def import_superset_dashboard(zip_path: str, username: str, flask_app_path: str = "superset.app:create_app()"):
    """
    Import a single dashboard zip into Superset under the given username.
    """
    if not os.path.exists(zip_path):
        print(f"❌ Dashboard file not found: {zip_path}")
        return

    env = os.environ.copy()
    env["FLASK_APP"] = flask_app_path

    try:
        print(f"⏳ Importing dashboard from {zip_path} as user '{username}'...")
        subprocess.run(
            ["superset", "import-dashboards", "--path", zip_path, "--username", username],
            check=True,
            env=env
        )
        print(f"✅ Dashboard import completed from {zip_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Dashboard import failed for {zip_path}: {e}")

def import_dashboards_from_config(config):
    dashboard_paths = config["paths"].get("dashboard_zip") or config["paths"].get("fixed_dashboard_zip")

    # Fallback to latest ZIP if dashboard_zip is not set
    if not dashboard_paths:
        print("ℹ️ No dashboard path in config — using latest ZIP file from folder.")
        dashboard_paths = get_latest_dashboard_zips()
    elif isinstance(dashboard_paths, str):
        dashboard_paths = [dashboard_paths]

    username = config["superset_admin"]["username"]
    flask_app_path = config["paths"].get("superset_config", "superset.app:create_app()")

    for zip_path in dashboard_paths:
        import_superset_dashboard(zip_path, username, flask_app_path)
