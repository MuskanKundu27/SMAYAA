# Build the web app on this (Windows) machine and upload it to the server.
# The server is too small to build it comfortably, so only the finished files are sent.
#
#   powershell -ExecutionPolicy Bypass -File deploy\push-web.ps1 -Server 3.110.175.240 -Key $HOME\.ssh\smayaa-key.pem

param(
    [Parameter(Mandatory = $true)][string]$Server,
    [Parameter(Mandatory = $true)][string]$Key,
    [string]$User = "ubuntu"
)
$ErrorActionPreference = "Stop"
$web = Join-Path $PSScriptRoot "..\web"
$archive = Join-Path $env:TEMP "smayaa-web.tar.gz"

Push-Location $web
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Web build failed" }
    tar -czf $archive -C dist .
} finally {
    Pop-Location
}

scp -i $Key $archive "${User}@${Server}:/tmp/smayaa-web.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Upload failed" }
# Replace the old files in one step, so visitors never see a half-uploaded site.
ssh -i $Key "${User}@${Server}" "set -e; rm -rf /tmp/smayaa-web && mkdir /tmp/smayaa-web && tar -xzf /tmp/smayaa-web.tar.gz -C /tmp/smayaa-web && chmod -R a+rX /tmp/smayaa-web && sudo rm -rf /var/www/smayaa.old && sudo mv /var/www/smayaa /var/www/smayaa.old && sudo mv /tmp/smayaa-web /var/www/smayaa && sudo rm -rf /var/www/smayaa.old && rm /tmp/smayaa-web.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Install on server failed" }
Remove-Item $archive
Write-Host "Web app uploaded."
