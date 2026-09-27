$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$processed = Join-Path $workspaceRoot "backend\data\processed"
$cities = Import-Csv (Join-Path $processed "cities.csv")
$placeDestinations = Import-Csv (Join-Path $processed "places.csv") |
    ForEach-Object { $_.destination.Trim() } |
    Where-Object { $_ } |
    Sort-Object -Unique

$originLocations = @(
    foreach ($city in $cities) {
        $latitude = 0.0
        $longitude = 0.0
        if (
            $city.name -and
            [double]::TryParse($city.latitude, [ref]$latitude) -and
            [double]::TryParse($city.longitude, [ref]$longitude)
        ) {
            [pscustomobject]@{
                city = $city.name.Trim()
                country = "India"
                lat = $latitude
                lng = $longitude
                normalized = $city.normalized_name
                aliases = ConvertFrom-Json $city.aliases -ErrorAction SilentlyContinue
            }
        }
    }
)

$destinationLocations = [System.Collections.Generic.List[object]]::new()
foreach ($destination in $placeDestinations) {
    $normalizedDestination = $destination.ToLowerInvariant()
    $match = $originLocations |
        Where-Object {
            $_.city -ieq $destination -or
            $_.normalized -ieq $normalizedDestination -or
            $_.aliases -contains $destination
        } |
        Select-Object -First 1

    if ($match -and -not ($destinationLocations.city -contains $match.city)) {
        $destinationLocations.Add([pscustomobject]@{
            city = $match.city
            country = $match.country
            lat = $match.lat
            lng = $match.lng
        })
    }
}

$catalog = [pscustomobject]@{
    origins = @($originLocations | ForEach-Object {
        [pscustomobject]@{
            city = $_.city
            country = $_.country
            lat = $_.lat
            lng = $_.lng
        }
    })
    destinations = @($destinationLocations)
}

$outputPath = Join-Path $PSScriptRoot "..\public\locations.json"
$json = $catalog | ConvertTo-Json -Depth 4 -Compress
[System.IO.File]::WriteAllText($outputPath, $json, [System.Text.UTF8Encoding]::new($false))
Write-Host "Wrote $($catalog.origins.Count) origins and $($catalog.destinations.Count) supported destinations to $outputPath"
