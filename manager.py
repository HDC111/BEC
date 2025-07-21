import subprocess
import os
import shutil
import tkinter as tk
from scripts.init_case import init_case
from tkinter import filedialog
from database.database import load_dataframes_to_postgres
from scripts.psy_database import create_db_and_user
from scripts.data_swap import swap_dataset
from scripts.run_microsoft_extractor import open_gui
from datetime import datetime
from scripts.matcher import run_matcher
from scripts.test_create_case_dashboard import import_dashboard, clone_and_swap
import yaml
import sys
import tempfile
import socket
import time
from scripts.dashboards_import import import_superset_dashboard, get_latest_dashboard_zips
import webbrowser
# === Load Configuration ===
def load_config():
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)

# === GUI File Selector and Copier ===
def select_and_store_log_file(config):
    print("📂 Please select a raw UAL log file...")
    root = tk.Tk()
    root.withdraw()
    selected_file = filedialog.askopenfilename(
        title="Select UAL log file",
        filetypes=[("Log files", "*.csv *.json *.xlsx"), ("All files", "*.*")]
    )
    if not selected_file:
        print("❌ No file selected.")
        return None

    input_dir = os.path.abspath(config["paths"]["input_dir"])
    os.makedirs(input_dir, exist_ok=True)

    stored_path = os.path.join(input_dir, "UAL.csv")
    shutil.copy(selected_file, stored_path)

    print(f"✅ UAL file saved to: {stored_path}")
    return os.path.abspath(stored_path)

# === Run Analyzer with PowerShell ===
def run_analyzer(input_file, config):
    print("🔍 Running MC Analyzer...")

    if not os.path.exists(input_file):
        print("❌ Input file not found.")
        return

    analyzer_script = os.path.abspath(config["scripts"]["analyzer"])
    output_dir = os.path.join(config["paths"]["current_case"], "processed")
    os.makedirs(output_dir, exist_ok=True)

    command = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", analyzer_script,
        "-Path", input_file,
        "-OutputDir", output_dir
    ]

    try:
        subprocess.run(command, check=True)
        print(f"✅ Analyzer output saved to: {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Analyzer failed: {e}")
        raise

# === Run Parser and IP Geolocation ===
def run_parser_on_file(input_file_path, config):
    print("🧹 Parsing UAL file...")

    parser_script = os.path.abspath(config["scripts"]["parser"])
    ip_parser_script = os.path.abspath(config["scripts"]["ip_parser"])
    output_file = os.path.join(config["paths"]["current_case"], "processed", "output_accessed.xlsx")


    env = os.environ.copy()
    env["UAL_INPUT_FILE"] = input_file_path
    env["UAL_OUTPUT_FILE"] = output_file

    try:
        subprocess.run([sys.executable, parser_script], check=True, env=env)
        print(f"✅ Parsing complete. Output saved to: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Parser or IP script failed: {e}")
        raise

# === Run Suspicious Matcher ===
def run_suspicious_marker(config):
    print("🚩 Running suspicious matcher...")

    script_path = os.path.abspath(config["scripts"]["suspicious_marker"])
    try:
        subprocess.run([sys.executable, script_path], check=True)
        print(f"✅ Suspicious records marked and saved.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Suspicious matcher failed: {e}")
        raise


def setup_superset_first_time(config):
    print("🛠 Running first-time Superset setup...")

    superset_config_path = os.path.abspath(config["paths"]["superset_config"])
    env = os.environ.copy()
    env["SUPERSET_CONFIG_PATH"] = superset_config_path
    env["FLASK_APP"] = "superset"

    admin = config.get("superset_admin", {})
    try:
        subprocess.run(["superset", "db", "upgrade"], check=True, env=env)

        subprocess.run([
            "superset", "fab", "create-admin",
            "--username", admin["username"],
            "--firstname", admin["firstname"],
            "--lastname", admin["lastname"],
            "--email", admin["email"],
            "--password", admin["password"]
        ], check=True, env=env)

        subprocess.run(["superset", "init"], check=True, env=env)

        print("✅ Superset initialized.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Superset setup failed: {e}")

def launch_superset(config):
    print("🚀 Launching Apache Superset...")

    superset_config_path = os.path.abspath(config["paths"]["superset_config"])
    env = os.environ.copy()

    env["SUPERSET_CONFIG_PATH"] = superset_config_path
    env["FLASK_APP"] = "superset"

    try:
        subprocess.Popen(["superset", "run", "-p", "8088"], env=env)
        print("✅ Superset is launching on http://localhost:8088")
    except Exception as e:
        print(f"❌ Failed to launch Superset: {e}")


def register_superset_database(config):
    print("🔗 Registering PostgreSQL database in Superset...")

    env = os.environ.copy()
    env["SUPERSET_CONFIG_PATH"] = os.path.abspath(config["paths"]["superset_config"])
    env["FLASK_APP"] = "superset"

    pg = config["postgres"]

    # Create a temporary YAML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
        tmp_file.write(f"""
databases:
  - database_name: "{pg['name']}"
    sqlalchemy_uri: "{pg['sqlalchemy_uri']}"
""")
        tmp_file_path = tmp_file.name

    try:
        subprocess.run(["superset", "import-datasources", "--path", tmp_file_path], check=True, env=env)
        print("✅ Superset DB registered.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to register Superset DB: {e}")


def wait_for_superset_ready(host="localhost", port=8088, timeout=30):
    print("⏳ Waiting for Superset API to become available...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                print("✅ Superset is ready.")
                return True
        except OSError:
            time.sleep(1)
    print("❌ Superset did not start in time.")
    return False

def run_create_superset_datasets():
    print("📦 Running dataset creation script...")
    try:
        subprocess.run([sys.executable, "scripts/create_superset_datasets.py"], check=True)
        print("✅ Superset datasets created successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Dataset creation failed: {e}")
'''
def import_superset_dashboards(config):
    print("📥 Importing Superset dashboards...")
    env = os.environ.copy()
    env["SUPERSET_CONFIG_PATH"] = os.path.abspath(config["paths"]["superset_config"])
    env["FLASK_APP"] = "superset"

    export_path = os.path.abspath(config["paths"]["dashboard_zip"])
    admin_user = config["superset_admin"]["username"]

    if not os.path.exists(export_path):
        print(f"❌ Dashboard export not found at {export_path}")
        return

    try:
        subprocess.run([
            "superset", "import-dashboards",
            "--path", export_path,
            "--username", admin_user,
            "--force"
        ], check=True, env=env)
        print("✅ Dashboard imported successfully.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to import dashboard: {e}")'''
def run_latest_dashboard_import():
    config = load_config()
    username = config["superset_admin"]["username"]

    # Get the newest zip(s) — change `count=3` if you want more
    latest_zips = get_latest_dashboard_zips(folder="superset_exports", count=1)

    if not latest_zips:
        print("⚠️ No dashboard ZIPs found to import.")
        return

    for zip_path in latest_zips:
        import_superset_dashboard(zip_path, username)


# === Main ===
def main():
    
    open_gui()
    config = init_case()
    
    input_file = select_and_store_log_file(config)
    

    if input_file and os.path.exists(input_file):
        
        


        run_analyzer(input_file, config)

        run_parser_on_file(input_file, config)
        
        run_matcher(config)
        
        create_db_and_user(config)

        load_dataframes_to_postgres(config)


        
        answer_setup = input("First time using Superset? Run setup? (y/n): ").strip().lower()
        
        if answer_setup == 'y':
            setup_superset_first_time(config)

        register_superset_database(config)

        answer_launch = input("Do you want to launch Superset now and create datasets? (y/n): ").strip().lower()
        if answer_launch == 'y':
            launch_superset(config)
            if wait_for_superset_ready():
                run_create_superset_datasets()
                case_id = os.path.basename(config["paths"]["current_case"]).replace("case_", "")
                table_name = f"case_{case_id}_marked_records"

                print("📦 Running Superset dataset creation script...")
                try:
                    subprocess.run([sys.executable, "scripts/create_superset_datasets.py", table_name], check=True)
                    print("✅ Superset dataset created successfully.")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Dataset creation failed: {e}")
                print("📥 Importing and preparing dashboard...")
                try:
                    zip_path = config["paths"]["dashboard_zip"]
                    username = config["superset_admin"]["username"]
                    password = config["superset_admin"]["password"]

                    superset_config_path = os.path.abspath(config["paths"]["superset_config"])
                    powershell_set_env = f'''
                    $env:FLASK_APP = "superset"
                    $env:SUPERSET_CONFIG_PATH = "{superset_config_path}"
                    '''

                    # Run it in a persistent PowerShell session so Superset CLI sees the env
                    subprocess.run(["powershell", "-Command", powershell_set_env], shell=True)

                    env = os.environ.copy()
                    env["FLASK_APP"] = "superset"
                    env["SUPERSET_CONFIG_PATH"] = superset_config_path


                    if import_dashboard(zip_path, username, password,env):
                        time.sleep(2)
                        print("🌀 Cloning dashboard, charts, and updating filters...")
                        try:
                            subprocess.run([sys.executable, "scripts/clone_dashboard_swap_dataset.py"], check=True,env=env, cwd=os.getcwd())
                            print("Ready to read")
                        except subprocess.CalledProcessError as e:
                            print(f"❌ Dashboard cloning and filter update failed: {e}")

                except Exception as e:
                    print(f"Dashboard import and setup failed: {e}")

    else:
        print("❌ File could not be used. Check upload and copy step.")

if __name__ == "__main__":
    main()
