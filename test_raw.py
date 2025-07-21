import pandas as pd
import json

def parse_auditdata(auditdata_str):
    try:
        return json.loads(auditdata_str)
    except Exception:
        return {}

def is_axios_access(audit_obj):
    actor_info = audit_obj.get('ActorInfoString', '') or ''
    client_info = audit_obj.get('ClientInfoString', '') or ''
    combined = f"{actor_info} {client_info}".lower()
    return 'axios' in combined

def extract_all_message_items(audit_obj):
    records = []
    folders = audit_obj.get('Folders', [])
    actor_info = audit_obj.get('ActorInfoString', 'Unknown')

    if not isinstance(folders, list):
        return records

    for folder in folders:
        folder_items = folder.get('FolderItems', [])
        if not isinstance(folder_items, list):
            continue

        for item in folder_items:
            if isinstance(item, dict):
                msg_id = item.get('InternetMessageId')  # may be None
                size = item.get('SizeInBytes', 0)
                records.append({
                    'actorinfostring': actor_info.strip(),
                    'internetmessageid': str(msg_id).strip() if msg_id else None,
                    'size_bytes': int(size) if pd.notna(size) else 0
                })
    return records

def count_all_axios_message_ids_including_null(filepath):
    df = pd.read_csv(filepath)
    df.columns = [col.strip().lower() for col in df.columns]
    audit_col = 'auditdata'

    all_records = []

    for idx, row in df.iterrows():
        audit_raw = row.get(audit_col)
        if pd.isna(audit_raw):
            continue

        audit_json = parse_auditdata(audit_raw)

        if is_axios_access(audit_json):
            extracted = extract_all_message_items(audit_json)
            all_records.extend(extracted)

    extracted_df = pd.DataFrame(all_records)

    if extracted_df.empty:
        print("🚫 No axios-accessed records found.")
        return

    # Deduplicate by actor + message ID + size
    deduped_df = extracted_df.drop_duplicates(subset=['actorinfostring', 'internetmessageid', 'size_bytes'])

    # Group by actor
    grouped = deduped_df.groupby('actorinfostring', dropna=False)

    print("\n📊 Summary by ActorInfoString:")
    summary_rows = []
    for actor, group in grouped:
        total_records = len(group)
        total_size = group['size_bytes'].sum()
        null_ids = group['internetmessageid'].isna().sum()

        print(f"\n👤 Actor: {actor}")
        print(f"   - Total unique records: {total_records}")
        print(f"   - Total size (bytes): {total_size:,}")
        print(f"   - Null Message IDs: {null_ids}")

        summary_rows.append({
            'actorinfostring': actor,
            'total_unique_records': total_records,
            'total_size_bytes': total_size,
            'null_message_ids': null_ids
        })

    summary_df = pd.DataFrame(summary_rows)

    # Optional: return all deduped data
    return deduped_df, summary_df

# === Example usage ===
if __name__ == '__main__':
    input_csv = 'UAL-1May25-21May25.csv'  # Replace with your actual file
    result_df, summary_df = count_all_axios_message_ids_including_null(input_csv)

    # Optional: Save results
    # result_df.to_csv('deduped_axios_records.csv', index=False)
    # summary_df.to_csv('axios_summary_by_actor.csv', index=False)
