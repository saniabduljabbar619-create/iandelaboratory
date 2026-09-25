# scripts/lan/copy_cloud_to_lan.ps1
#
# One-time: copy the cloud (Aiven) database onto this LAN server PC's MySQL,
# then prepare it for sync. Run from the project folder in PowerShell:
#
#   $env:AIVEN_DB_PASSWORD = "<aiven password>"
#   $env:LAN_DB_PASSWORD   = "<local solunex user password>"
#   .\scripts\lan\copy_cloud_to_lan.ps1
#
# The cloud must ALREADY be running the new code with SYNC_ENABLED=true
# before you run this (docs/LAN_OFFLINE_MODE.md, step 1).

param(
    [string]$AivenHost = "i-and-e-mysql-saniabduljabbar619-caa2.l.aivencloud.com",
    [int]$AivenPort    = 22695,
    [string]$AivenUser = "avnadmin",
    [string]$AivenDb   = "defaultdb",
    [string]$LanUser   = "solunex",
    [string]$LanDb     = "solunex_lan",
    [string]$DumpFile  = "cloud_copy.sql"
)
$ErrorActionPreference = "Stop"

if (-not $env:AIVEN_DB_PASSWORD) { throw "Set `$env:AIVEN_DB_PASSWORD first." }
if (-not $env:LAN_DB_PASSWORD)   { throw "Set `$env:LAN_DB_PASSWORD first." }

Write-Host "1/3 Downloading the cloud database..."
# --result-file instead of '>' : PowerShell redirection would write UTF-16 and corrupt the dump.
& mysqldump --host=$AivenHost --port=$AivenPort --user=$AivenUser "--password=$env:AIVEN_DB_PASSWORD" `
    --ssl-mode=REQUIRED --single-transaction --set-gtid-purged=OFF --no-tablespaces `
    --routines --triggers "--result-file=$DumpFile" $AivenDb
if ($LASTEXITCODE -ne 0) { throw "mysqldump failed" }

Write-Host "2/3 Loading it into local MySQL ($LanDb)..."
cmd /c "mysql --user=$LanUser --password=$env:LAN_DB_PASSWORD $LanDb < $DumpFile"
if ($LASTEXITCODE -ne 0) { throw "import failed" }

Write-Host "3/3 Preparing the copy for sync..."
& python -m app.sync.cli init-lan
if ($LASTEXITCODE -ne 0) { throw "init-lan failed" }

Remove-Item $DumpFile   # contains patient data; don't leave it lying around
Write-Host "Done. Start the server with scripts\lan\start_server.bat"
