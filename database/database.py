import pandas as pd
from sqlalchemy import create_engine
import os
import yaml

def load_dataframes_to_postgres(config):

    # Create engine
    sqlalchemy_uri = config["postgres"]["sqlalchemy_uri"]
    engine = create_engine(sqlalchemy_uri)

    # Get case identifier
    case_id = os.path.basename(config["paths"]["current_case"]).replace("case_", "")
    prefix = f"case_{case_id}_"

    # Only process this file
    filename = "output_accessed_marked.xlsx"
    table_name = f"{prefix}marked_records"

    file_path = os.path.join(config["paths"]["current_case"], "processed", filename)

    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return
    except Exception as e:
        print(f"❌ Failed to load {file_path}: {e}")
        return

    # Normalize columns
    df.columns = df.columns.str.strip().str.lower()

    if "creationdate" in df.columns:
        df["creationdate"] = pd.to_datetime(
            df["creationdate"].astype(str),
            format="%d/%m/%Y %I:%M:%S %p",
            errors='coerce'
        )
        df["creation_day"] = df["creationdate"].dt.strftime('%Y-%m-%d')
        df["creation_time"] = df["creationdate"].dt.strftime('%H:%M:%S')

    try:
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        print(f"✅ Written to table: {table_name}")
    except Exception as e:
        print(f"❌ Failed to write {table_name} to database: {e}")

