# run_full_repo_scan.ps1 -- Comprehensive read-only forensic scanner for ROS_RE
$repoRoot = "c:\Users\Raysoo\Downloads\ROS_RE"
$patterns = @(
    "*loginapp*", "*baseapp*", "*cellapp*", "*dbapp*", "*bots*", "*reviver*",
    "*bwserver*", "*bigworld*", "*server.xml*", "*server.conf*", "*server_config*",
    "*.pubkey", "*.privkey", "*.key", "*.pem", "*.pub", "*.crt",
    "*.npk", "*.pak", "*.obb", "*.zip", "*.7z", "*.tar", "*.gz",
    "*.so", "*.dll", "*.exe"
)

Write-Host "Scanning repository: $repoRoot"

$files = Get-ChildItem -Path $repoRoot -Recurse -File -Include $patterns -ErrorAction SilentlyContinue

Write-Host "Found $($files.Count) candidate files. Computing SHA-256 hashes..."

$results = foreach ($f in $files) {
    # Skip .git internal pack files unless directly relevant
    if ($f.FullName -like "*\.git\*") { continue }
    
    try {
        $hashObj = Get-FileHash -Algorithm SHA256 -Path $f.FullName -ErrorAction Stop
        $hash = $hashObj.Hash
    } catch {
        $hash = "ERROR: " + $_.Exception.Message
    }
    
    [PSCustomObject]@{
        FullName     = $f.FullName
        Name         = $f.Name
        Length       = $f.Length
        LastModified = $f.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        SHA256       = $hash
    }
}

$results | Export-Clixml -Path "$repoRoot\scratch\scan_results.xml"
$results | Export-Csv -Path "$repoRoot\scratch\scan_results.csv" -NoTypeInformation
Write-Host "Scanned $($results.Count) files successfully. Saved to scan_results.csv."
