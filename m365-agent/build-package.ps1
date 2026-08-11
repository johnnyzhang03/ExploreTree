param(
    [Parameter(Mandatory = $true)]
    [string]$McpServerUrl,

    [string]$TeamsAppId = [guid]::NewGuid().ToString(),

    [Parameter(Mandatory = $true)]
    [string]$PublisherEmail
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "appPackage"
$build = Join-Path $root "build"
$stage = Join-Path $build "appPackage"
$zip = Join-Path $build "ExploreTree.dev.zip"

if ($McpServerUrl -notmatch "^https://") {
    throw "McpServerUrl must be a public HTTPS origin."
}

if (Test-Path $stage) {
    Remove-Item $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Copy-Item (Join-Path $source "*") $stage -Recurse

Get-ChildItem $stage -File | Where-Object {
    $_.Extension -in ".json", ".txt"
} | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content.Replace('${{MCP_SERVER_URL}}', $McpServerUrl.TrimEnd("/"))
    $content = $content.Replace('${{TEAMS_APP_ID}}', $TeamsAppId)
    $content = $content.Replace('${{APP_NAME_SUFFIX}}', " dev")
    $content = $content.Replace("publisher-email@example.com", $PublisherEmail)
    Set-Content $_.FullName $content -NoNewline
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
Write-Host "Created $zip"
Write-Host "Teams app ID: $TeamsAppId"
