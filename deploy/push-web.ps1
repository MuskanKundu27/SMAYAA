# Build the web app on this (Windows) machine and upload it to the server.
# The server is too small to build it comfortably, so only the finished files are sent.
#
#   powershell -ExecutionPolicy Bypass -File deploy\push-web.ps1 -Server 3.110.175.240 -Key $HOME\.ssh\smayaa-key.pem
#   powershell -ExecutionPolicy Bypass -File deploy\push-web.ps1 -Server 43.239.93.107 -Port 22120 -User syamaa
# Without -Key, ssh uses your default key or asks for the password.

param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$Key = "",
    [string]$User = "ubuntu",
    [int]$Port = 22
)
$ErrorActionPreference = "Stop"
$web = Join-Path $PSScriptRoot "..\web"
$archive = Join-Path $env:TEMP "smayaa-web.tar.gz"
$sshArgs = @()
if ($Key) { $sshArgs += @("-i", $Key) }

Push-Location $web
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Web build failed" }
    tar -czf $archive -C dist .
} finally {
    Pop-Location
}

scp @sshArgs -P $Port $archive "${User}@${Server}:/tmp/smayaa-web.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Upload failed" }
# Replace the old files in one step, so visitors never see a half-uploaded site.
# -t gives sudo a terminal, in case the server user must type a password for sudo.
ssh -t @sshArgs -p $Port "${User}@${Server}" "set -e; rm -rf /tmp/smayaa-web && mkdir /tmp/smayaa-web && tar -xzf /tmp/smayaa-web.tar.gz -C /tmp/smayaa-web && chmod -R a+rX /tmp/smayaa-web && sudo rm -rf /var/www/smayaa.old && sudo mv /var/www/smayaa /var/www/smayaa.old && sudo mv /tmp/smayaa-web /var/www/smayaa && sudo rm -rf /var/www/smayaa.old && rm /tmp/smayaa-web.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Install on server failed" }
Remove-Item $archive
Write-Host "Web app uploaded."
