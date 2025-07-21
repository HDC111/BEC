import os
import shutil
import yaml
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog

def init_case(base_dir="cases", base_settings_path="config/settings.yaml"):
    """
    Create a date-named case folder with subdirectories and copy settings.yaml.
    Update config paths to the new case folder and return the config.
    """
    today_str = datetime.today().strftime("%Y%m%d")
    case_folder_name = f"case_{today_str}"
    case_path = Path(base_dir) / case_folder_name

    subdirs = ['saved', 'processed', 'marked', 'superset']
    case_path.mkdir(parents=True, exist_ok=True)
    print(f"[✔] Created case folder: {case_path}")

    for sub in subdirs:
        sub_path = case_path / sub
        sub_path.mkdir(exist_ok=True)
        print(f"[✔] Created subfolder: {sub_path}")

    # Copy settings.yaml into case folder
    settings_dst = case_path / 'settings.yaml'
    if not settings_dst.exists():
        shutil.copy(base_settings_path, settings_dst)
        print(f"[✔] Copied settings.yaml to: {settings_dst}")
    else:
        print(f"[!] settings.yaml already exists at: {settings_dst}, skipping copy.")

    # Load and update config
    with open(base_settings_path, "r") as f:
        config = yaml.safe_load(f)

    config["paths"]["current_case"] = str(case_path)
    config["paths"]["input_dir"] = str(case_path / "saved")

    # Save updated config into the case folder
    with open(settings_dst, "w") as f:
        yaml.dump(config, f)

    # ✅ Overwrite global config/settings.yaml to reflect the new case
    global_config_path = "config/settings.yaml"
    backup_config_path = "config/settings_backup.yaml"

    shutil.copy(global_config_path, backup_config_path)
    print(f"[✔] Backed up original config to: {backup_config_path}")

    with open(global_config_path, "w") as f:
        yaml.dump(config, f)
    print(f"[✔] Global config updated at: {global_config_path}")

    return config


def select_and_store_log_file(config):
    """
    Ask user to select a file and save it to current_case/saved/UAL.csv.
    Also updates config["paths"]["input_dir"] to match the saved folder.
    """
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

    case_path = config["paths"].get("current_case")
    if not case_path:
        raise ValueError("❌ 'current_case' is not set in config['paths'].")

    saved_path = os.path.join(case_path, "saved")
    os.makedirs(saved_path, exist_ok=True)

    stored_path = os.path.join(saved_path, "UAL.csv")
    shutil.copy(selected_file, stored_path)

    config["paths"]["input_dir"] = saved_path

    print(f"✅ UAL file saved to: {stored_path}")
    return stored_path


if __name__ == "__main__":
    # Step 1: Create case + update config
    config = init_case()

    # Step 2: Ask user to pick a log file and store it
    select_and_store_log_file(config)

    # Step 3: Backup and overwrite global config/settings.yaml
    global_config_path = "config/settings.yaml"
    backup_config_path = "config/settings_backup.yaml"

    shutil.copy(global_config_path, backup_config_path)
    print(f"[✔] Backed up original config to: {backup_config_path}")

    with open(global_config_path, "w") as f:
        yaml.dump(config, f)
    print(f"[✔] Global config updated at: {global_config_path}")
