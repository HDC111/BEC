import re
import ipaddress
import csv
import datetime
import os
import sys

input_file = os.getenv("UAL_INPUT_FILE", "UAL.csv")
 
try:
    import geoip2.database
except ImportError:
    print("❌ Required module 'geoip2' not found.")
    print("💡 Please install it using:")
    print("   sudo apt install python3-geoip2\n")
    exit(1)
 
VERSION = "2.0.0"
 
def print_intro():
    print("=" * 60)
    print("📄 Public IP Extractor & GeoIP/ASN Enricher")
    print(f"🔢 Version: {VERSION}")
    print(f"🕒 Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

# added method to bruteforce browser version issue , will think of better fix if problem arises again 

def browser_check(ip):
    browser_ips = []
    for i in range(128, 137):
        browser_ips.append(f'{i}.0.0.0')
 
    if ip == '9.0.0.0' or ip in browser_ips:
        return False
    else:
        return True
 
def extract_ips_from_csv(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
 
    ipv4_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ipv6_pattern = r'\b(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}\b'
 
    ipv4_matches = re.findall(ipv4_pattern, content)
    ipv6_matches = re.findall(ipv6_pattern, content)
 
    all_ips = set(ipv4_matches + ipv6_matches)
    public_ips = set()
 
    for ip_str in all_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if not (
                ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or
                ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified or
                not browser_check(str(ip_obj))
            ):
                public_ips.add(str(ip_obj))
        except ValueError:
            continue
 
    return sorted(public_ips)
 
def load_msft_ip_ranges(msft_csv_path):
    msft_ranges = []
    with open(msft_csv_path, 'r') as f:
        next(f)  # Skip header
        for line in f:
            prefix = line.strip().split(',')[0]
            try:
                msft_ranges.append(ipaddress.ip_network(prefix))
            except ValueError:
                continue
    return msft_ranges
 
def is_msft_ip(ip_str, msft_ranges):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return any(ip_obj in net for net in msft_ranges)
    except ValueError:
        return False
 
def geo_lookup(ip_list, city_db_path, asn_db_path, msft_ranges):
    results = []
 
    with geoip2.database.Reader(city_db_path) as city_reader, \
         geoip2.database.Reader(asn_db_path) as asn_reader:
 
        for ip in ip_list:
            entry = {'ClientIP': ip}
 
            # GeoIP city data
            try:
                city_resp = city_reader.city(ip)
                entry.update({
                    'Country': city_resp.country.name or 'N/A',
                    'City': city_resp.city.name or 'N/A',
                    'Latitude': city_resp.location.latitude,
                    'Longitude': city_resp.location.longitude
                })
            except geoip2.errors.AddressNotFoundError:
                entry.update({
                    'Country': 'N/A',
                    'City': 'N/A',
                    'Latitude': 'N/A',
                    'Longitude': 'N/A'
                })
 
            # ASN data
            try:
                asn_resp = asn_reader.asn(ip)
                entry.update({
                    'ASN': asn_resp.autonomous_system_number,
                    'ISP': asn_resp.autonomous_system_organization
                })
            except geoip2.errors.AddressNotFoundError:
                entry.update({
                    'ASN': 'N/A',
                    'ISP': 'N/A'
                })
 
            # Check for Microsoft fallback
            if entry['ISP'] == 'N/A' and is_msft_ip(ip, msft_ranges):
                entry['ISP'] = 'Microsoft'
                # Leave ASN as "N/A" unless you want to assign a custom value
 
            results.append(entry)
 
    return results
 
def save_to_csv(data, output_file='public_ips_geolocation_accessed.csv'):
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ClientIP', 'Country', 'City', 'Latitude', 'Longitude', 'ASN', 'ISP']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
 
if __name__ == '__main__':
    print_intro()
 
# ---- CONFIG ----
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.getenv("UAL_INPUT_FILE", os.path.join(script_dir, "UAL.csv"))
    city_db = os.path.join(script_dir, "GeoLite2-City.mmdb")
    asn_db = os.path.join(script_dir, "GeoLite2-ASN.mmdb")
    msft_ip_file = os.path.join(script_dir, "msft-public-ips.csv")
 
    # ---- PIPELINE ----
    ips = extract_ips_from_csv(input_file)
    msft_ranges = load_msft_ip_ranges(msft_ip_file)
    enriched_data = geo_lookup(ips, city_db_path=city_db, asn_db_path=asn_db, msft_ranges=msft_ranges)
    save_to_csv(enriched_data)
 
    print(f"\n✅ Saved {len(enriched_data)} public IPs with geo and ASN info to 'public_ips_geolocation_accessed.csv'")
