param([ValidateSet('firefox','webkit')] [string]$Engine)
$root = (Resolve-Path "$PSScriptRoot/../../..").Path
$lab = "$root/.local/audit-ui-20261125"
$account = Get-Content -Raw "$lab/runtime.json" | ConvertFrom-Json
$env:E2E_ORIGIN = $account.origin
$env:E2E_LOCAL_USERNAME = $account.username
$env:E2E_LOCAL_PASSWORD = $account.password
$env:E2E_INVITE = $account.invite
$env:E2E_DISPOSABLE = "1"
$env:PLAYWRIGHT_BROWSERS_PATH = "$lab/pw-browsers"
Set-Location "$lab/web"
# Headless PDF generation in the existing print spec is a Chromium-specific Playwright operation.
& node node_modules/@playwright/test/cli.js test "--browser=$Engine" --grep-invert '列印指定' --reporter=list --trace=off "--output=$lab/$Engine-results" *> "$PSScriptRoot/$Engine-playwright.txt"
$code=$LASTEXITCODE
"Exit: $code" >> "$PSScriptRoot/$Engine-playwright.txt"
exit $code
