import csv
import json
import pandas as pd
import subprocess
import os

all_rows = []

# Read UAL CSV and flatten AuditData JSON
with open('UAL.csv', 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    headers = next(reader) 
    audit_data_index = headers.index("AuditData")

    for line in reader:
        try:
            json_obj = json.loads(line[audit_data_index])
            flat = pd.json_normalize(json_obj)

            base_row = {
                headers[i]: line[i]
                for i in range(len(headers))
                if i != audit_data_index
            }

            flat_dict = flat.iloc[0].to_dict()

            # Combine ClientIP / ClientIPAddress
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
subprocess.run(['python3', 'IP-parser.py'], check=True)

# Reload enriched output and geolocation CSV
df = pd.read_excel('output_accessed.xlsx')
geo_df = pd.read_csv('public_ips_geolocation_accessed.csv')

# Create lookup dictionary based on ClientIP
geo_lookup = geo_df.set_index('ClientIP')[['Country', 'City', 'ASN', 'ISP']].to_dict(orient='index')

# Add geolocation info based on ResolvedClientIP
for col in ['Country', 'City', 'ASN', 'ISP']:
    df[col] = df.apply(lambda row: geo_lookup.get(row.get('ResolvedClientIP'), {}).get(col, ""), axis=1)

# Reorder columns to place new fields right after ResolvedClientIP
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
df.to_excel('output_accessed.xlsx', index=False)
df.to_csv('output_accessed.csv', index=False)
