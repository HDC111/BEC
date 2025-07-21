import zipfile
import yaml
import os
import shutil
from pathlib import Path

def validate_yaml_in_superset_export(zip_path):
    temp_dir = Path("temp_validate_export")

    # Step 1: Clean old temp dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    # Step 2: Unzip the file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        print(f"✅ Extracted: {zip_path}")
    except Exception as e:
        print(f"❌ Failed to unzip {zip_path}: {e}")
        return

    # Step 3: Detect base directory inside temp
    contents = list(temp_dir.iterdir())
    if len(contents) == 1 and contents[0].is_dir():
        base_dir = contents[0]
        print(f"📁 Detected base folder inside ZIP: {base_dir.name}")
    else:
        base_dir = temp_dir

    # Step 4: Validate YAML files
    has_error = False
    for folder_name in ["dashboards", "charts", "datasets"]:
        folder = base_dir / folder_name
        if not folder.exists():
            print(f"⚠️ Folder missing: {folder_name}")
            continue

        for yaml_file in folder.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    print(f"⚠️ Not a valid YAML dict: {yaml_file}")
                    has_error = True
                else:
                    print(f"✅ Valid YAML: {yaml_file.name}")

            except Exception as e:
                print(f"❌ Failed to load {yaml_file.name}: {e}")
                has_error = True

    if not has_error:
        print("🎉 All YAML files look valid.")
    else:
        print("❗ Some files are invalid or incomplete.")

    # Clean up
    shutil.rmtree(temp_dir)

# === Run ===
if __name__ == "__main__":
    zip_path = "superset_exports/fixed_test_dashboard.zip"
    validate_yaml_in_superset_export(zip_path)
