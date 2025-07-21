import pandas as pd

# --- CONFIG ---
input_file = r"UAL.csv"      # Replace with your file name
output_file = "UAL_sample.csv"
date_column = "CreationDate"        # The column that contains the date & time

# --- Load Excel file ---
df = pd.read_csv(input_file)

# --- Convert to datetime (dayfirst=True for dd/mm/yyyy format) ---
df[date_column] = pd.to_datetime(df[date_column], errors='coerce', dayfirst=True)

# --- Filter by just the date portion ---
target_dates = [pd.Timestamp("2025-05-12"), pd.Timestamp("2025-05-13")]
filtered_df = df[df[date_column].dt.normalize().isin(target_dates)]

# --- Save to Excel ---
filtered_df.to_csv(output_file, index=False)

print(f"✅ Extracted {len(filtered_df)} records to '{output_file}'")
