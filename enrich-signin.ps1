# ====== CONFIGURATION ======
$inputFile = "SignInLogs.csv"                      # Path to your existing CSV
$outputFile = "SignInLogs_WithLocation.csv"        # Output enriched CSV
$ipinfoToken = "32be37657eef48"                   # Replace with your ipinfo token
$rateLimitDelayMs = 200                            # Delay between requests to avoid hitting rate limit

# ====== LOAD CSV AND DEDUPLICATE IPs ======
$rows = Import-Csv $inputFile
$uniqueIPs = $rows.IPAddress | Where-Object { $_ -and $_ -match '\d+\.\d+\.\d+\.\d+' } | Sort-Object -Unique

$ipLookup = @{}

foreach ($ip in $uniqueIPs) {
    try {
        $url = "https://ipinfo.io/$ip/json?token=$ipinfoToken"
        $response = Invoke-RestMethod -Uri $url

        $ipLookup[$ip] = @{
            City    = $response.city
            Region  = $response.region
            Country = $response.country
            Org     = $response.org
        }

        Start-Sleep -Milliseconds $rateLimitDelayMs
    }
    catch {
        Write-Warning "Failed to fetch data for IP $ip"
        $ipLookup[$ip] = @{
            City    = ""
            Region  = ""
            Country = ""
            Org     = ""
        }
    }
}

# ====== ENRICH ROWS ======
$enrichedRows = $rows | ForEach-Object {
    $ip = $_.IPAddress
    $geo = $ipLookup[$ip]

    $_ | Add-Member -NotePropertyName City -NotePropertyValue $geo.City -Force
    $_ | Add-Member -NotePropertyName Region -NotePropertyValue $geo.Region -Force
    $_ | Add-Member -NotePropertyName Country -NotePropertyValue $geo.Country -Force
    $_ | Add-Member -NotePropertyName Org -NotePropertyValue $geo.Org -Force
    $_
}

# ====== EXPORT TO CSV ======
$enrichedRows | Export-Csv -Path $outputFile -NoTypeInformation

Write-Host "✅ Done! Output saved to: $outputFile"
