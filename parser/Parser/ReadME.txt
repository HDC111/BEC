Version 2.0.0 - 18 June 2025 - Muhammed Tekin
There are two Python scripts that parse UAL. The "ual-file-parser-final-withAuditData.py" adds the AuditData column as an additional field.

- "ual-file-parser-final.py" does the following tasks:
	1. Expands the AuditData column;
	2. Executes "IP-parser.py" to find all IPs in the UAL file and saves to "public_ips_geolocation_accessed.csv";
	3. Merges "ClientIP" and "ClientIPAddress" columns into a new column "ResolvedClientIP";
	4. Looks up the "ResolvedClientIP" in the "public_ips_geolocation_accessed.csv" and adds Country, City, ASN and ISP as new columns; and
	5. Exports parsed file as "output_accessed.xlsx".	

- The input file should be named "UAL.csv" to work with the scripts.

Notes:
- Another field with "ActorIpAddress" was observed in the UAL AuditData. The test cases proved that the ActorIpAddress was always present in either "ClientIP" or "ClientIPAddress." Therefore, "ual-file-parser-final" only merges the "ClientIP" and "ClientIPAddress."

- Time taken for the test case with the UAL file that had 38,923 records: 
	1. "ual-file-parser-final.py" took 1 minute and 36 seconds; and
	2. "ual-file-parser-final.py" took 1 minute and 32 seconds.

