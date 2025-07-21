import csv
import json
import pandas as pd
import subprocess
import os
import sys

all_rows = []

# Read UAL CSV and flatten AuditData JSON
input_file = os.getenv("UAL_INPUT_FILE", "UAL.csv")
with open(input_file, 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    headers = next(reader) 
    audit_data_index = headers.index("AuditData")

    for line in reader:
        try:
            audit_data_raw = line[audit_data_index]
            json_obj = json.loads(audit_data_raw)
            flat = pd.json_normalize(json_obj)

            base_row = {
                headers[i]: line[i]
                for i in range(len(headers))
                if i != audit_data_index
            }

            flat_dict = flat.iloc[0].to_dict()

            # Add raw AuditData for debugging
            flat_dict["AuditDataRaw"] = audit_data_raw

            # Combine ClientIP and ClientIPAddress
            client_ip = flat_dict.get("ClientIP") or flat_dict.get("ClientIPAddress")
            flat_dict["ResolvedClientIP"] = client_ip

            merged = {**base_row, **flat_dict}
            all_rows.append(merged)

        except (json.JSONDecodeError, IndexError):
            continue

# Create flattened output
final_df = pd.DataFrame(all_rows)
final_df.to_excel('output_accessed.xlsx', index=False)

# Remove previous geolocation file if exists
geo_csv = 'public_ips_geolocation_accessed.csv'
if os.path.exists(geo_csv):
    os.remove(geo_csv)

# Run IP geolocation script
ip_parser_path = os.path.join(os.path.dirname(__file__), "IP-parser.py")
try:
    subprocess.run([sys.executable, ip_parser_path], check=True)
except subprocess.CalledProcessError as e:
    print(f"❌ Failed to run IP-parser.py: {e}")
    raise

# Reload enriched output and geolocation CSV
df = pd.read_excel('output_accessed.xlsx')
geo_df = pd.read_csv('public_ips_geolocation_accessed.csv')

# Create lookup dictionary based on ClientIP
geo_lookup = geo_df.set_index('ClientIP')[['Country', 'City', 'ASN', 'ISP']].to_dict(orient='index')

# Add geolocation info based on ResolvedClientIP
for col in ['Country', 'City', 'ASN', 'ISP']:
    df[col] = df.apply(lambda row: geo_lookup.get(row.get('ResolvedClientIP'), {}).get(col, ""), axis=1)

# Reorder columns to place Country, City, ASN, ISP right after ResolvedClientIP
cols = list(df.columns)
if 'ResolvedClientIP' in cols:
    ip_index = cols.index('ResolvedClientIP')
    for col in ['ISP', 'ASN', 'City', 'Country']:
        if col in cols:
            cols.remove(col)
    for col in reversed(['Country', 'City', 'ASN', 'ISP']):
        cols.insert(ip_index + 1, col)

df = df[cols]  # Apply new column order

# Save final enriched output
output_file = os.getenv("UAL_OUTPUT_FILE", "output_accessed.xlsx")
df.to_excel(output_file, index=False)
